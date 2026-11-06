#!/usr/bin/env python3
"""Add LAN diagnostics upload to the pinned HyperHLE iOS host.

The receiver is the companion Windows HTTP server on port 8765. This patch
uses Bonjour to discover the Windows receiver and uploads incremental log
segments during gameplay, queueing failed transfers for retry.
"""
from pathlib import Path
import plistlib
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: patch-hyperhle-lan-diagnostics.py NativeHost.swift Info.plist")

swift_path, plist_path = map(Path, sys.argv[1:])
source = swift_path.read_text()

marker = "private enum HyperHLEDiagnosticsUploader {"

uploader = r'''private final class HyperHLEBonjourDiscovery: NSObject, NetServiceBrowserDelegate, NetServiceDelegate {
    static let shared = HyperHLEBonjourDiscovery()
    private var browser: NetServiceBrowser?
    private var resolvingServices: [NetService] = []
    private var continuations: [CheckedContinuation<(String, Int)?, Never>] = []
    private var finished = false
    private var cachedReceiver: (String, Int)?

    func discover(timeout: TimeInterval = 4) async -> (String, Int)? {
        await withCheckedContinuation { continuation in
            DispatchQueue.main.async {
                if let cached = self.cachedReceiver {
                    continuation.resume(returning: cached)
                    return
                }
                self.continuations.append(continuation)
                guard self.browser == nil else { return }
                self.finished = false
                let browser = NetServiceBrowser()
                self.browser = browser
                browser.delegate = self
                browser.searchForServices(ofType: "_hyperhle-diag._tcp.", inDomain: "local.")
                DispatchQueue.main.asyncAfter(deadline: .now() + timeout) { [weak self] in
                    self?.finish(nil)
                }
            }
        }
    }

    func netServiceBrowser(_ browser: NetServiceBrowser, didFind service: NetService, moreComing: Bool) {
        guard !finished else { return }
        resolvingServices.append(service)
        service.delegate = self
        service.resolve(withTimeout: 5)
    }

    func netServiceDidResolveAddress(_ sender: NetService) {
        guard !finished, let host = sender.hostName?.trimmingCharacters(in: CharacterSet(charactersIn: ".")),
              !host.isEmpty, sender.port > 0 else { return }
        cachedReceiver = (host, sender.port)
        finish(cachedReceiver)
    }

    func netService(_ sender: NetService, didNotResolve errorDict: [String: NSNumber]) {}

    func netServiceBrowser(_ browser: NetServiceBrowser, didNotSearch errorDict: [String: NSNumber]) {
        finish(nil)
    }

    private func finish(_ result: (String, Int)?) {
        guard !finished else { return }
        finished = true
        browser?.stop()
        browser = nil
        resolvingServices.removeAll()
        let pending = continuations
        continuations.removeAll()
        pending.forEach { $0.resume(returning: result) }
    }
}

private enum HyperHLEDiagnosticsUploader {
    private static let queueName = "HyperHLE-UploadQueue"
    private static let lastSnapshotKey = "hyperhleDiagnosticsLastSnapshot"

    private static var liveTask: Task<Void, Never>?

    static func startLiveCapture() {
        guard liveTask == nil else { return }
        liveTask = Task.detached {
            while !Task.isCancelled {
                await uploadPending()
                try? await Task.sleep(nanoseconds: 3_000_000_000)
            }
        }
    }

    static func stopLiveCapture() {
        liveTask?.cancel()
        liveTask = nil
        Task { await uploadPending() }
    }

    static func uploadPending() async {
        let defaults = UserDefaults.standard
        let discovered = await HyperHLEBonjourDiscovery.shared.discover()
        let manualHost = defaults.string(forKey: "hyperhleDiagnosticsHost")?
            .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        let manualPort = Int(defaults.string(forKey: "hyperhleDiagnosticsPort") ?? "8765") ?? 8765
        let host = discovered?.0 ?? manualHost
        let port = discovered?.1 ?? manualPort
        guard !host.isEmpty, (1...65535).contains(port) else {
            print("HyperHLE LAN diagnostics: Bonjour receiver not found and no manual IP configured")
            return
        }
        print("HyperHLE LAN diagnostics: using receiver \(host):\(port)")

        let documents = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        let queue = documents.appendingPathComponent(queueName, isDirectory: true)
        do {
            try FileManager.default.createDirectory(at: queue, withIntermediateDirectories: true)
            try snapshotLogsIfChanged(documents: documents, queue: queue, defaults: defaults)
        } catch {
            print("HyperHLE LAN diagnostics: queue preparation failed: \(error)")
            return
        }

        let files = (try? FileManager.default.contentsOfDirectory(
            at: queue, includingPropertiesForKeys: nil
        ))?.filter { $0.pathExtension.lowercased() == "zip" }.sorted { $0.lastPathComponent < $1.lastPathComponent } ?? []

        guard !files.isEmpty else { return }
        guard let url = URL(string: "http://\(host):\(port)/upload") else { return }

        for file in files {
            do {
                var request = URLRequest(url: url)
                request.httpMethod = "POST"
                request.timeoutInterval = 60
                request.setValue(Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "unknown",
                                 forHTTPHeaderField: "X-HyperHLE-Build")
                request.setValue(Bundle.main.object(forInfoDictionaryKey: "HYPERHLE_GIT_COMMIT") as? String ?? "unknown",
                                 forHTTPHeaderField: "X-HyperHLE-Commit")
                request.setValue(UIDevice.current.model, forHTTPHeaderField: "X-HyperHLE-Device")
                let (_, response) = try await URLSession.shared.upload(for: request, fromFile: file)
                guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
                    print("HyperHLE LAN diagnostics: upload rejected for \(file.lastPathComponent)")
                    continue
                }
                try FileManager.default.removeItem(at: file)
                print("HyperHLE LAN diagnostics: uploaded \(file.lastPathComponent)")
            } catch {
                print("HyperHLE LAN diagnostics: upload deferred for \(file.lastPathComponent): \(error)")
            }
        }
    }

    private static func snapshotLogsIfChanged(
        documents: URL,
        queue: URL,
        defaults: UserDefaults
    ) throws {
        let names = ["touchhle-host.log", "touchhle-host-previous.log"]
        var entries: [(String, Data)] = []
        var newestStamp: TimeInterval = defaults.double(forKey: lastSnapshotKey)
        for name in names {
            let url = documents.appendingPathComponent(name)
            guard let data = try? Data(contentsOf: url), !data.isEmpty else { continue }
            let offsetKey = "hyperhleDiagnosticsOffset_\(name)"
            var offset = defaults.integer(forKey: offsetKey)
            if offset < 0 || offset > data.count { offset = 0 }
            guard data.count > offset else { continue }
            let delta = data.subdata(in: offset..<data.count)
            entries.append((name, delta))
            defaults.set(data.count, forKey: offsetKey)
            if let attributes = try? FileManager.default.attributesOfItem(atPath: url.path),
               let modified = attributes[.modificationDate] as? Date {
                newestStamp = max(newestStamp, modified.timeIntervalSince1970)
            }
        }
        guard !entries.isEmpty else { return }

        let metadata: [String: String] = [
            "app": "HyperHLE",
            "version": Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "unknown",
            "build": Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "unknown",
            "commit": Bundle.main.object(forInfoDictionaryKey: "HYPERHLE_GIT_COMMIT") as? String ?? "unknown",
            "device": UIDevice.current.model,
            "ios": UIDevice.current.systemVersion,
            "captured_at": ISO8601DateFormatter().string(from: Date())
        ]
        entries.append(("metadata.json", try JSONSerialization.data(withJSONObject: metadata, options: [.prettyPrinted, .sortedKeys])))
        let archive = makeStoredZip(entries)
        let name = "diagnostics-\(Int(Date().timeIntervalSince1970))-\(UUID().uuidString.prefix(8)).zip"
        try archive.write(to: queue.appendingPathComponent(name), options: .atomic)
        defaults.set(newestStamp, forKey: lastSnapshotKey)
    }

    // Minimal ZIP writer using STORE (method 0); no third-party package or
    // subprocess is needed on iOS. CRC-32 and central-directory records make
    // the result readable by Python zipfile and Windows Explorer.
    private static func crc32(_ data: Data) -> UInt32 {
        var crc: UInt32 = 0xffffffff
        for byte in data {
            crc ^= UInt32(byte)
            for _ in 0..<8 {
                crc = (crc & 1) != 0 ? (crc >> 1) ^ 0xedb88320 : crc >> 1
            }
        }
        return crc ^ 0xffffffff
    }

    private static func appendLE<T: FixedWidthInteger>(_ value: T, to data: inout Data) {
        var little = value.littleEndian
        withUnsafeBytes(of: &little) { data.append(contentsOf: $0) }
    }

    private static func makeStoredZip(_ entries: [(String, Data)]) -> Data {
        var output = Data()
        var central = Data()
        for (name, bytes) in entries {
            let filename = Data(name.utf8)
            let crc = crc32(bytes)
            let size = UInt32(bytes.count)
            let offset = UInt32(output.count)

            appendLE(UInt32(0x04034b50), to: &output)
            appendLE(UInt16(20), to: &output)
            appendLE(UInt16(0), to: &output)
            appendLE(UInt16(0), to: &output)
            appendLE(UInt16(0), to: &output)
            appendLE(UInt16(0), to: &output)
            appendLE(crc, to: &output)
            appendLE(size, to: &output)
            appendLE(size, to: &output)
            appendLE(UInt16(filename.count), to: &output)
            appendLE(UInt16(0), to: &output)
            output.append(filename)
            output.append(bytes)

            appendLE(UInt32(0x02014b50), to: &central)
            appendLE(UInt16(20), to: &central)
            appendLE(UInt16(20), to: &central)
            appendLE(UInt16(0), to: &central)
            appendLE(UInt16(0), to: &central)
            appendLE(UInt16(0), to: &central)
            appendLE(UInt16(0), to: &central)
            appendLE(crc, to: &central)
            appendLE(size, to: &central)
            appendLE(size, to: &central)
            appendLE(UInt16(filename.count), to: &central)
            appendLE(UInt16(0), to: &central)
            appendLE(UInt16(0), to: &central)
            appendLE(UInt16(0), to: &central)
            appendLE(UInt16(0), to: &central)
            appendLE(UInt32(0), to: &central)
            appendLE(offset, to: &central)
            central.append(filename)
        }
        let centralOffset = UInt32(output.count)
        output.append(central)
        appendLE(UInt32(0x06054b50), to: &output)
        appendLE(UInt16(0), to: &output)
        appendLE(UInt16(0), to: &output)
        appendLE(UInt16(entries.count), to: &output)
        appendLE(UInt16(entries.count), to: &output)
        appendLE(UInt32(central.count), to: &output)
        appendLE(centralOffset, to: &output)
        appendLE(UInt16(0), to: &output)
        return output
    }
}

'''
if marker not in source:
    anchor = "@objc(TouchHLENativeHost)\n"
    if source.count(anchor) != 1:
        raise SystemExit("could not locate TouchHLENativeHost insertion point")
    source = source.replace(anchor, uploader + anchor, 1)
elif "private enum HyperHLEDiagnosticsUploader {" not in source:
    raise SystemExit("unexpected uploader marker state")

# Start the app-level diagnostics service as soon as the iOS host launches.
start_anchor = '''    @objc class func start() {
        shared.presentLibrary()
    }'''
start_patch = '''    @objc class func start() {
        shared.presentLibrary()
        HyperHLEDiagnosticsUploader.startLiveCapture()
        Task { await HyperHLEDiagnosticsUploader.uploadPending() }
    }'''
if start_patch not in source:
    if source.count(start_anchor) != 1:
        raise SystemExit("could not patch native host startup retry")
    source = source.replace(start_anchor, start_patch, 1)

return_anchor = '''                self.isLaunching = false
                if result != 0 {'''
return_patch = '''                self.isLaunching = false
                Task { await HyperHLEDiagnosticsUploader.uploadPending() }
                if result != 0 {'''
if return_patch not in source:
    if source.count(return_anchor) != 1:
        raise SystemExit("could not patch game-return upload trigger")
    source = source.replace(return_anchor, return_patch, 1)

launch_anchor = '''                let result = EmulatorCore.withRunning(core) {'''
launch_patch = '''                HyperHLEDiagnosticsUploader.startLiveCapture()
                let result = EmulatorCore.withRunning(core) {'''
if launch_patch not in source:
    if source.count(launch_anchor) != 1:
        raise SystemExit("could not patch live upload start before game launch")
    source = source.replace(launch_anchor, launch_patch, 1)

# Keep the app-level diagnostics service alive when a game returns to the library.
# Do not stop live capture here: the host must keep streaming logs on the library screen.

# Add editable direct-IP settings and a real health-check action.
settings_start = source.index("private struct SettingsView: View {")
settings_end = source.index("private struct CoreChoiceRow", settings_start)
settings = source[settings_start:settings_end]
settings = settings.replace(
    "private struct SettingsView: View {",
    "private struct SettingsView: View {\n"
    '    @AppStorage("hyperhleDiagnosticsHost") private var diagnosticsHost = "192.168.1.138"\n'
    '    @AppStorage("hyperhleDiagnosticsPort") private var diagnosticsPort = "8765"\n'
    '    @State private var diagnosticsConnectionStatus = ""\n',
    1,
)
settings_anchor = '''                Section("Controls") {
                    Toggle("Analog Sticks Control Tilt", isOn: $analogTilt)
                }

                Section {
                    EnableJITButton()
'''
settings_replacement = '''                Section("Controls") {
                    Toggle("Analog Sticks Control Tilt", isOn: $analogTilt)
                }

                Section {
                    Text("Bonjour automatically searches for the Windows receiver. IP below is only a fallback.")
                    TextField("Windows PC IP", text: $diagnosticsHost)
                        .keyboardType(.URL)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    TextField("Port", text: $diagnosticsPort)
                        .keyboardType(.numberPad)
                    Button("Test connection") {
                        Task {
                            let host = diagnosticsHost.trimmingCharacters(in: .whitespacesAndNewlines)
                            let port = Int(diagnosticsPort) ?? 0
                            guard !host.isEmpty, (1...65535).contains(port),
                                  let url = URL(string: "http://\(host):\(port)/health") else {
                                diagnosticsConnectionStatus = "Invalid IP or port"
                                return
                            }
                            do {
                                let (_, response) = try await URLSession.shared.data(from: url)
                                if let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) {
                                    diagnosticsConnectionStatus = "Connection successful"
                                } else {
                                    diagnosticsConnectionStatus = "Receiver did not return HTTP 200"
                                }
                            } catch {
                                diagnosticsConnectionStatus = "Connection failed: \(error.localizedDescription)"
                            }
                        }
                    }
                    if !diagnosticsConnectionStatus.isEmpty {
                        Text(diagnosticsConnectionStatus).font(.footnote).foregroundStyle(.secondary)
                    }
                    Button("Upload saved diagnostics now") {
                        Task { await HyperHLEDiagnosticsUploader.uploadPending() }
                    }
                } header: {
                    Text("LAN Diagnostics")
                } footer: {
                    Text("Bonjour discovers the Windows receiver automatically. The diagnostics service starts with the app and uploads incremental log snapshots every few seconds on both the library screen and during gameplay; failed uploads are queued and retried.")
                }

                Section {
                    EnableJITButton()
'''
if settings_anchor not in settings:
    raise SystemExit("Controls/JIT insertion anchor not found")
settings=settings.replace(settings_anchor,settings_replacement);
source=source[:settings_start]+settings+source[settings_end:]
swift_path.write_text(source)

plist = plistlib.loads(plist_path.read_bytes())
plist["NSLocalNetworkUsageDescription"] = (
    "HyperHLE connects to your configured Windows PC and sends emulator diagnostic logs on your local network."
)
plist["NSBonjourServices"] = ["_hyperhle-diag._tcp"]
plist_path.write_bytes(plistlib.dumps(plist, fmt=plistlib.FMT_XML, sort_keys=False))
print("patched: iOS LAN diagnostics queue, ZIP upload, retry triggers, manual IP/port configuration and upload health check, and local-network privacy text")
