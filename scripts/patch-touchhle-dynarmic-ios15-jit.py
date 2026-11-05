#!/usr/bin/env python3
"""Patch only touchHLE Core B's Dynarmic JIT allocator for iOS 15.

The common HyperHLE patch installs a StikDebug BRK broker on physical iOS.
Core B on this iOS 15 target instead uses the traditional debugger-backed
RWX mapping and mprotect W^X transitions. macOS-only pthread JIT APIs and
MAP_JIT are deliberately not used on physical iOS.
"""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch-touchhle-dynarmic-ios15-jit.py DYNARMIC_SOURCE_DIR")

root = Path(sys.argv[1])
header = root / "externals/oaknut/include/oaknut/code_block.hpp"
if not header.is_file():
    raise SystemExit(f"Oaknut CodeBlock header not found: {header}")
text = header.read_text()


def replace_once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count == 0 and (not new or new in text):
        print(f"already patched: {label}")
        return
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one anchor, found {count}")
    text = text.replace(old, new, 1)
    print(f"patched: {label}")


broker_helpers = """#if defined(__APPLE__) && TARGET_OS_IPHONE && !TARGET_OS_SIMULATOR
namespace detail {

struct ReusableJitRegion {
    std::uint32_t* memory = nullptr;
    std::uint32_t* writable_memory = nullptr;
    std::size_t size = 0;
    bool in_use = false;
};

inline ReusableJitRegion& reusable_jit_region()
{
    static ReusableJitRegion region;
    return region;
}

__attribute__((noinline, optnone, naked)) static void* prepare_jit_region(void*, std::size_t)
{
    __asm__ volatile(
        "mov x16, #1\\n"
        "brk #0xf00d\\n"
        "ret\\n");
}

__attribute__((noinline, optnone, naked)) static void detach_jit_server()
{
    __asm__ volatile(
        "mov x16, #0\\n"
        "brk #0xf00d\\n"
        "ret\\n");
}

}  // namespace detail
#endif

"""
replace_once(broker_helpers, "", "remove StikDebug BRK broker helpers")

old_alloc = """#    if TARGET_OS_IPHONE && !TARGET_OS_SIMULATOR
        auto& reusable_region = detail::reusable_jit_region();
        if (reusable_region.memory != nullptr) {
            if (reusable_region.in_use || reusable_region.size != size)
                throw std::bad_alloc{};

            m_memory = reusable_region.memory;
            m_wmemory = reusable_region.writable_memory;
            reusable_region.in_use = true;
        } else {
            m_memory = (std::uint32_t*)detail::prepare_jit_region(nullptr, size);
            if (m_memory == nullptr)
                throw std::bad_alloc{};

            vm_prot_t current_protection;
            vm_prot_t maximum_protection;
            kern_return_t result = vm_remap(mach_task_self(),
                                            reinterpret_cast<vm_address_t*>(&m_wmemory),
                                            size,
                                            0,
                                            VM_FLAGS_ANYWHERE | VM_FLAGS_RANDOM_ADDR,
                                            mach_task_self(),
                                            reinterpret_cast<mach_vm_address_t>(m_memory),
                                            false,
                                            &current_protection,
                                            &maximum_protection,
                                            VM_INHERIT_NONE);
            if (result != KERN_SUCCESS ||
                vm_protect(mach_task_self(),
                           reinterpret_cast<vm_address_t>(m_wmemory),
                           size,
                           false,
                           VM_PROT_READ | VM_PROT_WRITE) != KERN_SUCCESS) {
                munmap(m_memory, size);
                throw std::bad_alloc{};
            }

            reusable_region = {m_memory, m_wmemory, size, true};
            m_should_detach_jit_server = true;
        }
#    elif TARGET_OS_IPHONE
"""
new_alloc = """#    if TARGET_OS_IPHONE && !TARGET_OS_SIMULATOR
        // iOS 15 debugger-backed JIT: one anonymous RWX mapping, with W^X
        // enforced by mprotect() in protect() and unprotect().
        m_memory = (std::uint32_t*)mmap(nullptr, size,
                                        PROT_READ | PROT_WRITE | PROT_EXEC,
                                        MAP_ANON | MAP_PRIVATE, -1, 0);
#    elif TARGET_OS_IPHONE
"""
replace_once(old_alloc, new_alloc, "use debugger-backed RWX mapping on physical iOS")

old_check = """#if defined(_WIN32)
        if (m_memory == nullptr)
#elif defined(__APPLE__) && TARGET_OS_IPHONE && !TARGET_OS_SIMULATOR
        if (m_memory == nullptr || m_wmemory == nullptr)
#else
        if (m_memory == MAP_FAILED)
#endif
            throw std::bad_alloc{};

#if !(defined(__APPLE__) && TARGET_OS_IPHONE && !TARGET_OS_SIMULATOR)
        m_wmemory = m_memory;
#endif
"""
new_check = """#if defined(_WIN32)
        if (m_memory == nullptr)
#else
        if (m_memory == MAP_FAILED)
#endif
            throw std::bad_alloc{};
"""
replace_once(old_check, new_check, "use MAP_FAILED allocation check")

old_dtor = """#    if defined(__APPLE__) && TARGET_OS_IPHONE && !TARGET_OS_SIMULATOR
        auto& reusable_region = detail::reusable_jit_region();
        if (reusable_region.memory == m_memory && reusable_region.writable_memory == m_wmemory) {
            reusable_region.in_use = false;
            return;
        }
        munmap(m_wmemory, m_size);
#    endif
        munmap(m_memory, m_size);
"""
replace_once(old_dtor, "        munmap(m_memory, m_size);\\n", "remove broker alias teardown")

replace_once("""#if defined(__APPLE__) && !TARGET_OS_IPHONE
        pthread_jit_write_protect_np(1);
#elif defined(__APPLE__) && TARGET_OS_IPHONE && TARGET_OS_SIMULATOR
""", """#if defined(__APPLE__) && !TARGET_OS_IPHONE
        pthread_jit_write_protect_np(1);
#elif defined(__APPLE__) && TARGET_OS_IPHONE && !TARGET_OS_SIMULATOR
        mprotect(m_memory, m_size, PROT_READ | PROT_EXEC);
#elif defined(__APPLE__) && TARGET_OS_IPHONE && TARGET_OS_SIMULATOR
""", "protect physical iOS JIT mapping with mprotect")

replace_once("""#if defined(__APPLE__) && !TARGET_OS_IPHONE
        pthread_jit_write_protect_np(0);
#elif defined(__APPLE__) && TARGET_OS_IPHONE && TARGET_OS_SIMULATOR
""", """#if defined(__APPLE__) && !TARGET_OS_IPHONE
        pthread_jit_write_protect_np(0);
#elif defined(__APPLE__) && TARGET_OS_IPHONE && !TARGET_OS_SIMULATOR
        mprotect(m_memory, m_size, PROT_READ | PROT_WRITE);
#elif defined(__APPLE__) && TARGET_OS_IPHONE && TARGET_OS_SIMULATOR
""", "unprotect physical iOS JIT mapping with mprotect")

replace_once("""    void detach_jit_server()
    {
#if defined(__APPLE__) && TARGET_OS_IPHONE && !TARGET_OS_SIMULATOR
        if (m_should_detach_jit_server) {
            m_should_detach_jit_server = false;
            detail::detach_jit_server();
        }
#endif
    }
""", """    // The traditional iOS 15 debugger JIT does not use a JIT broker.
    void detach_jit_server() {}
""", "remove JIT broker detach")

replace_once("""#if defined(__APPLE__) && TARGET_OS_IPHONE && !TARGET_OS_SIMULATOR
    bool m_should_detach_jit_server = false;
#endif
""", "", "remove JIT broker state")

if "brk #0xf00d" in text or "prepare_jit_region" in text or "detail::detach_jit_server" in text:
    raise SystemExit("StikDebug BRK broker code remains in Core B Dynarmic")
if "PROT_READ | PROT_WRITE | PROT_EXEC" not in text:
    raise SystemExit("RWX allocation was not installed")
if "mprotect(m_memory, m_size, PROT_READ | PROT_EXEC)" not in text:
    raise SystemExit("RX protection transition is missing")
if "mprotect(m_memory, m_size, PROT_READ | PROT_WRITE)" not in text:
    raise SystemExit("RW protection transition is missing")
if "pthread_jit_write_protect_np" in text:
    raise SystemExit("pthread_jit_write_protect_np must not be used for physical iOS")

header.write_text(text)
print(f"Core B iOS 15 debugger-backed JIT patch verified: {header}")
