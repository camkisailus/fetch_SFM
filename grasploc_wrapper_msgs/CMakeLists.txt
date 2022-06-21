cmake_minimum_required(VERSION 2.8.3)
project(grasploc_wrapper_msgs)

find_package(catkin REQUIRED COMPONENTS
  geometry_msgs
  sensor_msgs
  message_generation
  actionlib_msgs
)

add_action_files(
  DIRECTORY action
  FILES Grasploc.action GrasplocRequest.action
)

generate_messages(
  DEPENDENCIES
  sensor_msgs
  geometry_msgs
  actionlib_msgs
)

catkin_package(
  CATKIN_DEPENDS message_runtime geometry_msgs sensor_msgs actionlib_msgs
)
