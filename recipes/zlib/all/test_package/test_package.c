#include <stdio.h>
#include <stdlib.h>

#include <zlib.h>

int zlib_test_vsnprintf(void) {
#ifdef WITH_TEST_VSNPRINTF
    uLong flags = zlibCompileFlags();

    // 25th bit indicates vsnprinft support
    // 26th bit indicates whether vnsprinft returned void at compile time (i.e. doesn't work correctly)
    // from the zlib.h header:
    // > 25: 0 = *nprintf, 1 = *printf -- 1 means gzprintf() not secure!
    // > 26: 0 = returns value, 1 = void -- 1 means inferred string length returned
    if (flags >> 25 || flags >> 26) {
        printf("ZLIB is not compiled with vnsprinft support\n");
        return EXIT_FAILURE;
    }

    return EXIT_SUCCESS;
#else
    return EXIT_SUCCESS;
#endif
}

int main(void) {

    printf("ZLIB VERSION: %s\n", zlibVersion());

    return zlib_test_vsnprintf();
}
