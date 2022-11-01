#include "grasploc_wrapper/grasploc_wrapper.h"
#include <ros/console.h>

GrasplocWrapper::GrasplocWrapper()
  : loop_rate_(NULL)
  , new_pc_to_view_(false)
  , grasploc_as_(nh_, "grasploc", boost::bind(&GrasplocWrapper::GetGraspablePoints, this, _1), false) {
  int debug = 0;
  ros::NodeHandle private_nh("~");

  // Allocate variables to hold the value of ros params
  int num_samples;
  float neighborhood_radius;
  float max_grasper_aperture;
  float finger_width;
  float orient_radius;
  float distance_radius;
  float alignment_radius;
  int min_num_handle_inliers;
  int min_num_points_in_grasp;
  int max_num_points_intefering;
  float cb_x_min;
  float cb_x_max;
  float cb_y_min;
  float cb_y_max;
  float cb_z_min;
  float cb_z_max;


  // Get parameters from ros
  private_nh.param<int>("num_samples", num_samples, gloc_.GetNumSamples());
  private_nh.param<float>("neighborhood_radius", neighborhood_radius,
    gloc_.GetNeighborhoodRadius());
  private_nh.param<float>("max_grasper_aperture", max_grasper_aperture,
    gloc_.GetMaxGrasperAperture());
  private_nh.param<float>("finger_width", finger_width, gloc_.GetFingerWidth());
  private_nh.param<float>("orient_radius", orient_radius, gloc_.GetOrientRadius());
  private_nh.param<float>("distance_radius", distance_radius, gloc_.GetDistanceRadius());
  private_nh.param<float>("alignment_radius", alignment_radius, gloc_.GetAlignmentRadius());
  private_nh.param<int>("min_num_handle_inliers", min_num_handle_inliers,
    gloc_.GetMinNumHandleInliers());
  private_nh.param<int>("max_num_handles", max_num_handles_, 0);
  private_nh.param<bool>("visualize", visualize_, false);
  private_nh.param<int>("min_num_points_in_grasp", min_num_points_in_grasp,
    gloc_.GetMinNumPointsInGrasp());
  private_nh.param<int>("max_num_points_intefering", max_num_points_intefering,
    gloc_.GetMaxNumPointsInterfering());
  private_nh.param<float>("cb_x_min", cb_x_min, 0);
  private_nh.param<float>("cb_x_max", cb_x_max, 1);
  private_nh.param<float>("cb_y_min", cb_y_min, -0.41);
  private_nh.param<float>("cb_y_max", cb_y_max, 0.4);
  private_nh.param<float>("cb_z_min", cb_z_min, 0.6);
  private_nh.param<float>("cb_z_max", cb_z_max, 1.2);

  // Set all parameters
  gloc_.SetNumSamples(num_samples);
  gloc_.SetNeighborhoodRadius(neighborhood_radius);
  gloc_.SetMaxGrasperAperture(max_grasper_aperture);
  gloc_.SetFingerWidth(finger_width);
  gloc_.SetOrientRadius(orient_radius);
  gloc_.SetDistanceRadius(distance_radius);
  gloc_.SetAlignmentRadius(alignment_radius);
  gloc_.SetMinNumHandleInliers(min_num_handle_inliers);
  gloc_.SetMinNumPointsInGrasp(min_num_points_in_grasp);
  gloc_.SetMaxNumPointsInterfering(max_num_points_intefering);
  gloc_.SetCropBox(cb_x_max, cb_x_min, cb_y_max, cb_y_min, cb_z_max, cb_z_min);

  // Setup loop rate
  loop_rate_ = new ros::Rate(kLoopRate);
  update_cb_dims_ = nh_.subscribe("/kisailus/update_cb", 1000, &GrasplocWrapper::Update_Cropbox, this);
  // ros::Subscriber cropbox_dim_sub = private_nh.subscribe("/kisailus/update_cb_dims", )
  // Start action server
  grasploc_as_.start();
}

void GrasplocWrapper::Update_Cropbox(const grasploc_wrapper_msgs::CropBoxDimsConstPtr& msg)
{
  gloc_.SetCropBox(msg->x_max, msg->x_min, msg->y_max, msg->y_min, msg->z_max, msg->z_min);
  ROS_WARN("New x_min %f", msg->x_min);
  ROS_WARN("New x_max %f", msg->x_max);
  ROS_WARN("New y_min %f", msg->y_min);
  ROS_WARN("New y_max %f", msg->y_max);
  ROS_WARN("New z_min %f", msg->z_min);
  ROS_WARN("New z_max %f", msg->z_max);
}

GrasplocWrapper::~GrasplocWrapper() {
  if (loop_rate_ != NULL) delete loop_rate_;
}

void GrasplocWrapper::GetGraspablePoints(const grasploc_wrapper_msgs::GrasplocGoalConstPtr& goal) {
  // TODO(Kevin): Handle preempt correctly might need to start thread for gloc_.Run()
  // Generate pcl data type
  pcl::PCLPointCloud2 pcl_pc2;
  pcl_conversions::toPCL(goal->input_pc, pcl_pc2);
  Grasploc::GrasplocPC::Ptr grasploc_pc(new Grasploc::GrasplocPC);
  pcl::fromPCLPointCloud2(pcl_pc2, *grasploc_pc);

  // Run grasploc
  gloc_.SetViewpoint(goal->viewpoint.x, goal->viewpoint.y, goal->viewpoint.z);
  current_grasp_points_ = gloc_.Run(grasploc_pc, max_num_handles_);

  // Check if preempt
  if (grasploc_as_.isPreemptRequested()) {
    grasploc_as_.setPreempted();
    return;
  }

  // View the new input pc whether or not it has any graspable points
  new_pc_to_view_ = true;

  // Failed to find any graspable points
  if (current_grasp_points_->size() == 0) {
    grasploc_as_.setAborted();
    return;
  }

  grasploc_wrapper_msgs::GrasplocResult res;
  res.graspable_points.header.frame_id = "base_link";
  // Construct result
  for (Grasploc::GraspablePoints::iterator it = current_grasp_points_->begin();
       it != current_grasp_points_->end();
       ++it)
  {
    Grasploc::GraspablePoint& grasp_point = *it;

    // TODO(Kevin): Double check that axis are unit normal
    Eigen::Matrix3f rot;
    rot.col(0) = -grasp_point.normal_axis;
    rot.col(1) = grasp_point.principal_axis;
    rot.col(2) = rot.col(0).cross(rot.col(1));

    Eigen::Matrix3f rot_x;
    rot_x(0,0)=1;
    rot_x(1,0)=0;
    rot_x(2,0)=0;
    rot_x(0,1)=0;
    rot_x(1,1)=0;
    rot_x(2,1)=1;
    rot_x(0,2)=0;
    rot_x(1,2)=-1;
    rot_x(2,2)=0;
    rot = rot * rot_x;

    Eigen::Quaternion<float> eigen_quat(rot);
    geometry_msgs::Quaternion quat;
    quat.x = eigen_quat.x();
    quat.y = eigen_quat.y();
    quat.z = eigen_quat.z();
    quat.w = eigen_quat.w();

    geometry_msgs::Point centroid;
    centroid.x = grasp_point.shell.centroid(0);
    centroid.y = grasp_point.shell.centroid(1);
    centroid.z = grasp_point.shell.centroid(2);

    geometry_msgs::Pose pose;
    Eigen::Affine3d p = Eigen::Translation3d(centroid.x, centroid.y, centroid.z)*Eigen::Quaterniond(quat.w, quat.x, quat.y, quat.z);
    p = p * Eigen::Translation3d(-0.165, 0, 0);
    pose.position.x = p.translation().x();
    pose.position.y = p.translation().y();
    pose.position.z = p.translation().z();
    pose.orientation = quat;

    geometry_msgs::Vector3 normal;
    normal.x = grasp_point.normal_axis.x();
    normal.y = grasp_point.normal_axis.y();
    normal.z = grasp_point.normal_axis.z();

    geometry_msgs::Vector3 principal;
    principal.x = grasp_point.principal_axis.x();
    principal.y = grasp_point.principal_axis.y();
    principal.z = grasp_point.principal_axis.z();

    res.graspable_points.poses.push_back(pose);
    res.normal.push_back(normal);
    res.principal.push_back(principal);
  }

  if (grasploc_as_.isPreemptRequested()) {
    grasploc_as_.setPreempted();
    return;
  }

  grasploc_as_.setSucceeded(res);
}

void GrasplocWrapper::Run() {
  while (ros::ok()) {
    // Handle ros callbacks
    ros::spinOnce();

    // Handle visualization
    // TODO(Kevin): Make visualization thread safe
    if (visualize_) {
      // Update the viewer if needed
      if (new_pc_to_view_) {
        new_pc_to_view_ = false;
        simpleVis(viewer_, *current_grasp_points_.get(),
          gloc_.GetInputPointCloud());
      }

      // Check if this is the viewer exist and is not stoped
      if (viewer_) {
        if (!viewer_->wasStopped()) {
          // Update viewer for up to 100ms
          viewer_->spinOnce(100);
        } else {
          // The user closed the viewer so we don't need to do any more visualization
          visualize_ = false;
        }
      }
    }

    // Maintain loop rate
    loop_rate_->sleep();
  }
}

const float GrasplocWrapper::kLoopRate = 10;
