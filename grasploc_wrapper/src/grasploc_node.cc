#include "ros/ros.h"
#include "geometry_msgs/PoseArray.h"
#include "grasploc_wrapper_msgs/GrasplocAction.h"
#include "grasploc_wrapper_msgs/GrasplocRequestAction.h"
#include "grasploc.h"
#include "tf/transform_listener.h"
#include "pcl_conversions/pcl_conversions.h"
#include "pcl_ros/transforms.h"
#include "sensor_msgs/PointCloud2.h"
#include "std_msgs/Bool.h"
#include "actionlib/client/simple_action_client.h"
#include "actionlib/server/simple_action_server.h"


class GrasplocNode
{
  public:
    GrasplocNode(): ac_("grasploc", true)
      ,as_(nh_, "grasploc_requests", boost::bind(&GrasplocNode::grasp_callback, this, _1), false)
    {
      
      
      listener_ = new tf::TransformListener();
      grasp_pub_ = nh_.advertise<geometry_msgs::PoseArray>("grasploc", 1);
      pc_sub_ = nh_.subscribe("/head_camera/depth/points", 1, &GrasplocNode::pc_callback, this);
      // requestGraspSub_ = nh_.subscribe("request_grasp_pts", 1, &GrasplocNode::grasp_callback, this);
      as_.start();
      // Setup action client
      ROS_INFO("Waiting for grasploc action server");
      ac_.waitForServer();
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

    void grasp_callback(const grasploc_wrapper_msgs::GrasplocRequestGoalConstPtr& request) {
        
        ROS_INFO("Processing the pc to find graspable points");
          grasploc_wrapper_msgs::GrasplocRequestResult res;
          // Construct request
          grasploc_wrapper_msgs::GrasplocGoal goal;
          goal.input_pc = current_pc_;

          // Call action server
          ac_.sendGoal(goal);
          if (ac_.waitForResult()) {
            grasploc_wrapper_msgs::GrasplocResultConstPtr result = ac_.getResult();
            
            res.graspable_points.header.frame_id = "base_link";
            const int num_poses = result->graspable_points.poses.size();
            for(int i = 0; i < num_poses; i++){
              res.graspable_points.poses.push_back(result->graspable_points.poses.at(i));
            }
            // res.graspable_points.poses = result->graspable_points;
            // Publish message
            grasp_pub_.publish(result->graspable_points);
            as_.setSucceeded(res);
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
    actionlib::SimpleActionClient<grasploc_wrapper_msgs::GrasplocAction> ac_;
    actionlib::SimpleActionServer<grasploc_wrapper_msgs::GrasplocRequestAction> as_;
};



int main(int argc, char **argv) {
  ros::init(argc, argv, "grasploc_demo");
  GrasplocNode foo;
  while (ros::ok()) {
    ros::spinOnce();
  } 
}
