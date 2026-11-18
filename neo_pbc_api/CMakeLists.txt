# This CMake file is used by Conan as part of the UVC build process.
# It is not used by the PBC firmware build process.

add_library(pbc_protos STATIC pbc.proto)
protobuf_generate(TARGET pbc_protos LANGUAGE cpp)

target_include_directories(pbc_protos PUBLIC ${CMAKE_CURRENT_BINARY_DIR})
target_link_libraries(pbc_protos protobuf::libprotobuf)
