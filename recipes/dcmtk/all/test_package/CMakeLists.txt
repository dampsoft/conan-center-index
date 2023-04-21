cmake_minimum_required(VERSION 3.1)
project(test_package)

set(CMAKE_CXX_STANDARD 11)
find_package(DCMTK REQUIRED CONFIG)

add_executable(${PROJECT_NAME} test_package.cpp)
target_link_libraries(${PROJECT_NAME} dcmdata)
