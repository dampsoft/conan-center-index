cmake_minimum_required(VERSION 3.8)
project(test_package LANGUAGES CXX)

find_package(opentelemetry-cpp REQUIRED CONFIG)

add_executable(${CMAKE_PROJECT_NAME} test_package.cpp)
target_link_libraries(${CMAKE_PROJECT_NAME} PRIVATE opentelemetry-cpp::opentelemetry-cpp)
