#!/usr/bin/env python3
"""Add LAN diagnostics upload to the pinned HyperHLE iOS host.

The receiver is the companion Windows HTTP server on port 8765. This patch
uses a configured LAN address (no Bonjour dependency), keeps failed ZIPs in
Documents/HyperHLE-UploadQueue, and retries them at app start / game exit.
"""
from pathlib import Path
import plistlib
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: patch-hyperhle-lan-diagnostics.py NativeHost.swift Info.plist")

swift_path, plist_path = map(Path, sys.argv[1:])
source = swift_path.read_text()

marker = "private enum HyperHLEDiagnosticsUploader {"
uploader = r'''
private enum HyperHLEDiagnosticsUploader {
    private static let queueName = "HyperHLE-UploadQueue"
    private static let hostKey = "hyperhleDiagnosticsHost"
    private static let tokenKey = "hyperhleDiagnosticsToken"
    private static let lastSnapshotKey = "hyperhleDiagnosticsLastSnapshot"

    static func uploadPending() async {
        let defaults = UserDefaults.standard
        let host = (defaults.string(forKey: hostKey) ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        let token = (defaults.string(forKey: tokenKey) ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        guard !host.isEmpty, !token.isEmpty else { return }

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
        guard var components = URLComponents(string: host.contains("://") ? host : "http://\(host)") else { return }
        if components.port == nil { components.port = 8765 }
        components.path = "/upload"
        guard let url = components.url else { return }

        for file in files {
            do {
                var request = URLRequest(url: url)
                request.httpMethod = "POST"
                request.timeoutInterval = 60
                request.setValue(token, forHTTPHeaderField: "X-HyperHLE-Token")
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
        var newestStamp: TimeInterval = 0
        for name in names {
            let url = documents.appendingPathComponent(name)
            guard let attributes = try? FileManager.default.attributesOfItem(atPath: url.path),
                  let modified = attributes[.modificationDate] as? Date,
                  let data = try? Data(contentsOf: url), !data.isEmpty else { continue }
            newestStamp = max(newestStamp, modified.timeIntervalSince1970)
            entries.append((name, data))
        }
        guard !entries.isEmpty,
              newestStamp > defaults.double(forKey: lastSnapshotKey) else { return }

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

# Retry queued archives whenever the app returns to its library.
start_anchor = '''    @objc class func start() {
        shared.presentLibrary()
    }'''
start_patch = '''    @objc class func start() {
        shared.presentLibrary()
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

# Add fixed-IP and receiver-token settings in the existing Settings screen.
settings_start = source.index("private struct SettingsView: View {")
settings_end = source.index("private struct CoreChoiceRow", settings_start)
settings = source[settings_start:settings_end]
if "hyperhleDiagnosticsHost" not in settings:
    property_anchor = '''    @AppStorage("defaultCore") private var defaultCoreRaw = ""'''
    property_patch = property_anchor + '''
    @AppStorage("hyperhleDiagnosticsHost") private var diagnosticsHost = ""
    @AppStorage("hyperhleDiagnosticsToken") private var diagnosticsToken = ""'''
    if settings.count(property_anchor) != 1:
        raise SystemExit("could not locate SettingsView AppStorage properties")
    settings = settings.replace(property_anchor, property_patch, 1)
    advanced_anchor = '''                Section("Advanced") {'''
    diagnostics_section = '''                Section {
                    TextField("Windows PC IP (e.g. 192.168.1.20)", text: $diagnosticsHost)
                        .keyboardType(.URL)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    SecureField("Upload token", text: $diagnosticsToken)
                    Button("Upload saved diagnostics now") {
                        Task { await HyperHLEDiagnosticsUploader.uploadPending() }
                    }
                } header: {
                    Text("LAN Diagnostics")
                } footer: {
                    Text("Set the Windows receiver IP and token once. Logs upload automatically after a game exits and are retried on the next launch if the PC is unavailable. Port 8765 is used automatically.")
                }

'''
    if settings.count(advanced_anchor) != 1:
        raise SystemExit("could not locate SettingsView Advanced section")
    settings = settings.replace(advanced_anchor, diagnostics_section + advanced_anchor, 1)
    source = source[:settings_start] + settings + source[settings_end:]

swift_path.write_text(source)

plist = plistlib.loads(plist_path.read_bytes())
plist["NSLocalNetworkUsageDescription"] = (
    "HyperHLE sends emulator diagnostic logs to your Windows PC on your local network."
)
plist_path.write_bytes(plistlib.dumps(plist, fmt=plistlib.FMT_XML, sort_keys=False))
print("patched: iOS LAN diagnostics queue, ZIP upload, retry triggers, Settings fields, and local-network privacy text")
