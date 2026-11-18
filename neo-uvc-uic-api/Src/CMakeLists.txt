add_library(uic_protos STATIC UvcServices.proto)
protobuf_generate(TARGET uic_protos)

target_include_directories(uic_protos PUBLIC ${CMAKE_CURRENT_BINARY_DIR})
target_link_libraries(uic_protos protobuf::libprotobuf)
