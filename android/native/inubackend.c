/*
 * InuYasha Offline backend launcher (R7.7 / R7.8).
 *
 * Packaged as lib/armeabi/libinubackend.so so the Android PackageManager
 * extracts it into nativeLibraryDir with apk_data_file SELinux label and 0755
 * permissions. Before starting CPython, it links any libpymod_<name>.so in
 * nativeLibraryDir into $INUYASHA_DYNLOAD_DIR/<name>.cpython-311.so so CPython
 * loads C extensions via symlink from nativeLibraryDir (W^X / SELinux safe,
 * survives APK updates that rotate /data/app/~~.../lib/arm paths).
 */
#include <dirent.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

extern int Py_BytesMain(int argc, char **argv);

static void sync_dynload_symlinks(void) {
    const char *lib_dir = getenv("INUYASHA_NATIVE_LIB_DIR");
    const char *dyn_dir = getenv("INUYASHA_DYNLOAD_DIR");
    if (!lib_dir || !dyn_dir || !lib_dir[0] || !dyn_dir[0]) {
        return;
    }
    mkdir(dyn_dir, 0700);
    DIR *d = opendir(lib_dir);
    if (!d) {
        return;
    }
    const char *prefix = "libpymod_";
    const size_t prefix_len = strlen(prefix);
    const char *suffix = ".so";
    const size_t suffix_len = strlen(suffix);
    struct dirent *ent;
    char target[1024];
    char linkpath[1024];
    char modname[256];
    while ((ent = readdir(d)) != NULL) {
        const char *name = ent->d_name;
        size_t len = strlen(name);
        if (len <= prefix_len + suffix_len) {
            continue;
        }
        if (strncmp(name, prefix, prefix_len) != 0) {
            continue;
        }
        if (strcmp(name + len - suffix_len, suffix) != 0) {
            continue;
        }
        size_t mod_len = len - prefix_len - suffix_len;
        if (mod_len >= sizeof(modname)) {
            continue;
        }
        memcpy(modname, name + prefix_len, mod_len);
        modname[mod_len] = '\0';
        snprintf(target, sizeof(target), "%s/%s", lib_dir, name);
        snprintf(linkpath, sizeof(linkpath), "%s/%s.cpython-311.so", dyn_dir, modname);
        unlink(linkpath);
        symlink(target, linkpath);
    }
    closedir(d);
}

int main(int argc, char **argv) {
    setvbuf(stdout, NULL, _IOLBF, 0);
    setvbuf(stderr, NULL, _IOLBF, 0);
    sync_dynload_symlinks();
    return Py_BytesMain(argc, argv);
}
