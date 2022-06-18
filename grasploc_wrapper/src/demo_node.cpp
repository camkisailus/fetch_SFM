#include <iostream>

#include "ros/ros.h"
#include "geometry_msgs/PoseArray.h"
#include "grasploc_wrapper_msgs/GrasplocAction.h"
#include "grasploc.h"
#include "tf/transform_listener.h"
#include "pcl_conversions/pcl_conversions.h"
#include "pcl_ros/transforms.h"
#include "sensor_msgs/PointCloud2.h"
#include "actionlib/client/simple_action_client.h"

// Flag for if user requested a new pc
bool pc_requested = false;
// Flag for if pc recieved and transformed
bool pc_recieved = false;
sensor_msgs::PointCloud2 current_pc;
tf::TransformListener* listener;

void Callback(const sensor_msgs::PointCloud2::ConstPtr& msg) {
  // Return if no point cloud is requested
  if (!pc_requested) return;

  // Generate pcl data type in base_link
  std::string source_frame = "/head_camera_rgb_optical_frame";
  std::string target_frame = "/base_link";
  tf::StampedTransform transform;
  try {
    // Transform PC
    listener->waitForTransform(target_frame, source_frame, ros::Time(0), ros::Duration(10.0));
    pcl_ros::transformPointCloud(target_frame, *msg, current_pc, *listener);

    // Reset flags
    pc_recieved = true;
    pc_requested = false;
    ROS_INFO("Got a new pc and transformed to base_link");
  }
  catch(tf::TransformException ex) {
    ROS_ERROR("%s", ex.what());
    ros::Duration(1.0).sleep();
  }
}

int main(int argc, char **argv) {
  ros::init(argc, argv, "grasploc_demo");
  // Once the last nh is destroyed ros is shutdown
  ros::NodeHandle nh;

  // Setup tf listener
  listener = new tf::TransformListener();

  // Setup action client
  actionlib::SimpleActionClient<grasploc_wrapper_msgs::GrasplocAction> ac("grasploc", true);
  ROS_INFO("Waiting for grasploc action server");
  ac.waitForServer();
  ROS_INFO("Grasploc action server up");

  // Setup pc subscriber and grasp pos publisher
  ros::Subscriber sub = nh.subscribe("/head_camera/depth/points", 1, Callback);
  ros::Publisher pub = nh.advertise<geometry_msgs::PoseArray>("grasploc", 1);

  // Define the loop rate in hz
  ros::Rate loop_rate(10);

  while (ros::ok()) {
    if (pc_recieved) {
      ROS_INFO("Processing the pc to find graspable points");

      // Reset flag
      pc_recieved = false;
      // Construct request
      grasploc_wrapper_msgs::GrasplocGoal goal;
      goal.input_pc = current_pc;

      // Call action server
      ac.sendGoal(goal);
      if (ac.waitForResult()) {
        grasploc_wrapper_msgs::GrasplocResultConstPtr result = ac.getResult();
        // Publish message
        pub.publish(result->graspable_points);
        ROS_INFO("Published graspable points");
      } else {
        ROS_WARN("Didn't find any graspable points");
      }
    } else if (!pc_requested) {
      ROS_INFO("Press enter to send next cloud:");
      std::cin.clear();
      std::cin.ignore(INT_MAX, '\n');
      pc_requested = true;
      ROS_INFO("Waiting for next point cloud");
    }

    ros::spinOnce();
    loop_rate.sleep();
  }
}
