cmake_minimum_required(VERSION 2.8.3)
project(grasploc2.0)

find_package(PCL 1.7 REQUIRED)
set(PCL_Boost_LIBRARIES ${Boost_LIBRARIES})
set(PCL_Boost_DEFINITIONS ${Boost_DEFINITIONS})
set(PCL_Boost_INCLUDE_DIRS ${Boost_INCLUDE_DIRS})
# find_package(Eigen3 REQUIRED)
find_package(Boost REQUIRED COMPONENTS program_options)

include_directories(
  include
  ${PCL_INCLUDE_DIRS}
  ${Eigen3_INCLUDE_DIRS}
  ${Boost_INCLUDE_DIRS}
  ${PCL_Boost_INCLUDE_DIRS}
)

add_definitions(${PCL_DEFINITIONS})
add_definitions(${Eigen3_DEFINITIONS})
add_definitions(${Boost_DEFINITIONS})
add_definitions(${PCL_Boost_DEFINITIONS})

add_executable(main src/main.cpp src/grasploc.cpp src/util.cpp)

target_link_libraries(main
  ${PCL_LIBRARIES}
  ${Eigen3_LIBRARIES}
  ${Boost_LIBRARIES}
  ${PCL_Boost_LIBRARIES}
)
