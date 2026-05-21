cmake_minimum_required(VERSION 3.15)
project(route_planner LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(Python COMPONENTS Interpreter Development REQUIRED)
execute_process(
    COMMAND ${Python_EXECUTABLE} -m pybind11 --cmakedir
    OUTPUT_VARIABLE pybind11_DIR
    OUTPUT_STRIP_TRAILING_WHITESPACE
)
find_package(pybind11 CONFIG REQUIRED)

pybind11_add_module(
    route_planner
    planner.cpp
    bindings.cpp
)

target_include_directories(route_planner PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
target_compile_options(route_planner PRIVATE -O3)
