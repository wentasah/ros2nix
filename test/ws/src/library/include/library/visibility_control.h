#ifndef LIBRARY__VISIBILITY_CONTROL_H_
#define LIBRARY__VISIBILITY_CONTROL_H_

// This logic was borrowed (then namespaced) from the examples on the gcc wiki:
//     https://gcc.gnu.org/wiki/Visibility

#if defined _WIN32 || defined __CYGWIN__
  #ifdef __GNUC__
    #define LIBRARY_EXPORT __attribute__ ((dllexport))
    #define LIBRARY_IMPORT __attribute__ ((dllimport))
  #else
    #define LIBRARY_EXPORT __declspec(dllexport)
    #define LIBRARY_IMPORT __declspec(dllimport)
  #endif
  #ifdef LIBRARY_BUILDING_LIBRARY
    #define LIBRARY_PUBLIC LIBRARY_EXPORT
  #else
    #define LIBRARY_PUBLIC LIBRARY_IMPORT
  #endif
  #define LIBRARY_PUBLIC_TYPE LIBRARY_PUBLIC
  #define LIBRARY_LOCAL
#else
  #define LIBRARY_EXPORT __attribute__ ((visibility("default")))
  #define LIBRARY_IMPORT
  #if __GNUC__ >= 4
    #define LIBRARY_PUBLIC __attribute__ ((visibility("default")))
    #define LIBRARY_LOCAL  __attribute__ ((visibility("hidden")))
  #else
    #define LIBRARY_PUBLIC
    #define LIBRARY_LOCAL
  #endif
  #define LIBRARY_PUBLIC_TYPE
#endif

#endif  // LIBRARY__VISIBILITY_CONTROL_H_
