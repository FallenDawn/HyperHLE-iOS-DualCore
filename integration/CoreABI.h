#ifndef HYPERHLE_DUALCORE_ABI_H
#define HYPERHLE_DUALCORE_ABI_H
/*
 * PROPOSED adapter boundary only.
 * Not an ABI exported by HyperHLE-Reborn or official touchHLE v0.3.0.
 * Do not load a core expecting these symbols until an adapter implements
 * this header and the host has matching lifecycle/ownership tests.
 */
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
#define HDC_ABI_VERSION 1u
typedef enum hdc_status {
    HDC_OK = 0,
    HDC_ERROR_INVALID_ARGUMENT = 1,
    HDC_ERROR_UNSUPPORTED = 2,
    HDC_ERROR_INITIALIZATION = 3,
    HDC_ERROR_LOAD_GAME = 4,
    HDC_ERROR_RUNTIME = 5
} hdc_status;
typedef struct hdc_host_callbacks {
    uint32_t struct_size;
    void *context;
    void (*log)(void *context, int level, const char *message);
    void (*request_redraw)(void *context);
} hdc_host_callbacks;
typedef struct hdc_core_info {
    uint32_t struct_size;
    uint32_t abi_version;
    const char *identifier;
    const char *display_name;
    const char *version;
    uint64_t capabilities;
} hdc_core_info;
/* Adapter implementation and symbol export are pending. */
hdc_status hdc_get_core_info(hdc_core_info *out_info);
hdc_status hdc_initialize(const hdc_host_callbacks *callbacks);
hdc_status hdc_load_game(const char *app_bundle_path);
hdc_status hdc_start(void);
hdc_status hdc_pause(void);
hdc_status hdc_resume(void);
hdc_status hdc_stop(void);
void hdc_shutdown(void);
#ifdef __cplusplus
}
#endif
#endif
