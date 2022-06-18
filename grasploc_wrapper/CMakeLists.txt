cmake_minimum_required(VERSION 2.8.3)
project(grasploc_wrapper)

find_package(PCL 1.7 REQUIRED)
# find_package(Eigen3 REQUIRED)
# find_package(Boost REQUIRED)

add_definitions(${PCL_DEFINITIONS})
add_definitions(${Eigen3_DEFINITIONS})
add_definitions(${Boost_DEFINITIONS})

## Find catkin macros and libraries
find_package(catkin REQUIRED COMPONENTS
  roscpp
  sensor_msgs
  std_msgs
  geometry_msgs
  grasploc_wrapper_msgs
  pcl_ros
  pcl_conversions
  tf
)

###################################
## catkin specific configuration ##
###################################
## The catkin_package macro generates cmake config files for your package
## Declare things to be passed to dependent projects
## INCLUDE_DIRS: uncomment this if you package contains header files
## LIBRARIES: libraries you create in this project that dependent projects also need
## CATKIN_DEPENDS: catkin_packages dependent projects also need
## DEPENDS: system dependencies of this project that dependent projects also need
catkin_package(
  INCLUDE_DIRS include
  CATKIN_DEPENDS roscpp sensor_msgs std_msgs grasploc_wrapper_msgs
)

###########
## Build ##
###########
include_directories(
  ${catkin_INCLUDE_DIRS}
  include
  src/grasploc2.0/include
  ${PCL_INCLUDE_DIRS}
  ${Eigen3_INCLUDE_DIRS}
  ${Boost_INCLUDE_DIRS}
)

## Declare a C++ executable
add_executable(${PROJECT_NAME}_node
  src/grasploc_wrapper_node.cpp
  src/grasploc_wrapper.cpp
  src/grasploc2.0/src/grasploc.cpp
  src/grasploc2.0/src/util.cpp
)
 target_link_libraries(${PROJECT_NAME}_node
  ${catkin_LIBRARIES}
  ${PCL_LIBRARIES}
  ${Eigen3_LIBRARIES}
  ${Boost_LIBRARIES}
)
add_dependencies(${PROJECT_NAME}_node
  ${catkin_EXPORTED_TARGETS}
)

## Demo executable
# add_executable(demo_node
#   src/demo_node.cpp
# )
# target_link_libraries(demo_node
#   ${catkin_LIBRARIES}
# )
# add_dependencies(demo_node
#   ${catkin_EXPORTED_TARGETS}
# )

add_executable(grasploc_node
  src/grasploc_node.cc
)
target_link_libraries(grasploc_node
  ${catkin_LIBRARIES}
)
add_dependencies(grasploc_node
  ${catkin_EXPORTED_TARGETS}
)

