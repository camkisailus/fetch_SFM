#ifndef INCLUDE_GRASPLOC_WRAPPER_H_
#define INCLUDE_GRASPLOC_WRAPPER_H_

#include "grasploc.h"
#include "grasploc_wrapper_msgs/GrasplocAction.h"
#include "ros/ros.h"
#include "sensor_msgs/PointCloud2.h"
#include "pcl/point_types.h"
#include "pcl/point_cloud.h"
#include "pcl/PCLPointCloud2.h"
#include "pcl_conversions/pcl_conversions.h"
#include "pcl_ros/transforms.h"
#include "geometry_msgs/Vector3.h"
#include "geometry_msgs/Point.h"
#include "geometry_msgs/Quaternion.h"
#include "std_msgs/Int8.h"
#include "tf/transform_listener.h"
#include "util.h"
#include "actionlib/server/simple_action_server.h"

class GrasplocWrapper {
 private:
  // 10 Hz for now
  static const float kLoopRate;
 private:
  ros::NodeHandle nh_;
  Grasploc gloc_;
  int max_num_handles_;
  ros::Rate* loop_rate_;
  actionlib::SimpleActionServer<grasploc_wrapper_msgs::GrasplocAction> grasploc_as_;
  boost::shared_ptr<Grasploc::GraspablePoints> current_grasp_points_;

  // Visualization
  bool visualize_;
  boost::shared_ptr<pcl::visualization::PCLVisualizer> viewer_;
  bool new_pc_to_view_;

 public:
  GrasplocWrapper();
  void GetGraspablePoints(const grasploc_wrapper_msgs::GrasplocGoalConstPtr& goal);
  void Run();
  ~GrasplocWrapper();
};

#endif  // INCLUDE_GRASPLOC_WRAPPER_H_
