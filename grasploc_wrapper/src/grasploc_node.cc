#include "ros/ros.h"
#include "geometry_msgs/PoseArray.h"
#include "grasploc_wrapper_msgs/GrasplocAction.h"
#include "grasploc.h"
#include "tf/transform_listener.h"
#include "pcl_conversions/pcl_conversions.h"
#include "pcl_ros/transforms.h"
#include "sensor_msgs/PointCloud2.h"
#include "std_msgs/Bool.h"
#include "actionlib/client/simple_action_client.h"


class GrasplocNode
{
  public:
    GrasplocNode(): ac("grasploc", true)
    {
      
      
      listener_ = new tf::TransformListener();
      grasp_pub_ = nh_.advertise<geometry_msgs::PoseArray>("grasploc", 1);
      pc_sub_ = nh_.subscribe("/head_camera/depth/points", 1, &GrasplocNode::pc_callback, this);
      requestGraspSub_ = nh_.subscribe("request_grasp_pts", 1, &GrasplocNode::grasp_callback, this);
      // Setup action client
      ROS_INFO("Waiting for grasploc action server");
      ac.waitForServer();
      ROS_INFO("Grasploc action server up");
    }

    void pc_callback(const sensor_msgs::PointCloud2::ConstPtr& msg) {
      // Generate pcl data type in base_link
      std::string source_frame = "/head_camera_rgb_optical_frame";
      std::string target_frame = "/base_link";
      tf::StampedTransform transform;
      try {
        // Transform PC
        listener_->waitForTransform(target_frame, source_frame, ros::Time(0), ros::Duration(10.0));
        pcl_ros::transformPointCloud(target_frame, *msg, current_pc_, *listener_);
      }
      catch(tf::TransformException ex) {
        ROS_ERROR("%s", ex.what());
        ros::Duration(1.0).sleep();
      }
    }

    void grasp_callback(const std_msgs::Bool::ConstPtr& msg) {
        
        ROS_INFO("Processing the pc to find graspable points");

          // Construct request
          grasploc_wrapper_msgs::GrasplocGoal goal;
          goal.input_pc = current_pc_;

          // Call action server
          ac.sendGoal(goal);
          if (ac.waitForResult()) {
            grasploc_wrapper_msgs::GrasplocResultConstPtr result = ac.getResult();
            // Publish message
            grasp_pub_.publish(result->graspable_points);
          } else {
            ROS_WARN("Didn't find any graspable points");
          }
    }
  
  private:
    ros::NodeHandle nh_;
    sensor_msgs::PointCloud2 current_pc_;
    tf::TransformListener* listener_;
    ros::Publisher grasp_pub_;
    ros::Subscriber pc_sub_;
    ros::Subscriber requestGraspSub_;
    actionlib::SimpleActionClient<grasploc_wrapper_msgs::GrasplocAction> ac;
};



int main(int argc, char **argv) {
  ros::init(argc, argv, "grasploc_demo");
  GrasplocNode foo;
  while (ros::ok()) {
    ros::spinOnce();
  } 
}
