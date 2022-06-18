#ifndef INCLUDE_GRASPLOC_H_
#define INCLUDE_GRASPLOC_H_

#include <unsupported/Eigen/MatrixFunctions>
#include <stdint.h>
#include <math.h>
#include <iostream>
#include <string>
#include <vector>
#include <memory>
#include <set>

#include "pcl/point_types.h"
#include "pcl/features/normal_3d.h"
#include "pcl/filters/random_sample.h"
#include "pcl/kdtree/kdtree_flann.h"
#include "pcl/point_cloud.h"
#include "pcl/io/pcd_io.h"
#include "pcl/filters/filter.h"
#include "pcl/common/centroid.h"
#include "pcl/common/impl/eigen.hpp"
#include "pcl/common/transforms.h"

#include "Eigen/Dense"

class Grasploc {
  // Public data types
 public:
  // Convince typedefs for PCL types
  typedef pcl::PointXYZ GrasplocPoint;
  typedef pcl::PointCloud<GrasplocPoint> GrasplocPC;

  // Represents a cylindrical shell
  typedef struct {
    Eigen::Vector3f centroid;
    float radius;
    float extent;
      Eigen::Vector3f param;
  } Shell;

  // Defines a graspable point
  typedef struct {
    Eigen::Vector3f normal_axis;
    Eigen::Vector3f principal_axis;
    Shell shell;
    unsigned int handle_index;
  } GraspablePoint;
  typedef std::vector<GraspablePoint> GraspablePoints;

  // Private vars
 private:
  uint64_t num_samples_;
  float neighborhood_radius_;
  float max_grasper_aperture_;
  float finger_width_;
  float orient_radius_;
  float distance_radius_;
  float alignment_radius_;
  float cbx_max, cbx_min, cby_max, cby_min, cbz_max, cbz_min;
  unsigned int num_handles_;
  unsigned int min_num_handle_inliers_;
  Eigen::Vector3f viewpoint_;
  int min_num_points_in_grasp_;
  int max_num_points_intefering_;
  const float bad_point;
  GrasplocPC::Ptr input_pc_;

  // Public functions
 public:
  Grasploc(uint64_t num_samples = 2000, float neighborhood_radius = 0.025,
    float max_grasper_aperture = 0.110, float finger_width = 0.01,
    float orient_radius = 0.6, float distance_radius = 0.08,
    float alignment_radius = 0.02,
    unsigned int min_num_handle_inliers = 3,
    int min_num_points_in_grasp = 40,
    int max_num_points_intefering = 5);

  boost::shared_ptr<GraspablePoints> Run(std::string pcd_file_name,
    unsigned int num_handles = 1);
  boost::shared_ptr<GraspablePoints> Run(const GrasplocPC::ConstPtr pc,
    unsigned int num_handles = 1);

  void SetNumSamples(uint64_t num_samples);
  void SetNeighborhoodRadius(float  neighborhood_radius);
  void SetMaxGrasperAperture(float max_grasper_aperture);
  void SetFingerWidth(float finger_width);
  void SetOrientRadius(float orient_radius);
  void SetDistanceRadius(float distance_radius);
  void SetAlignmentRadius(float alignment_radius);
  void SetMinNumHandleInliers(unsigned int min_num_handle_inliers);
  void SetViewpoint(float x, float y, float z);
  void SetMinNumPointsInGrasp(int min_num_points_in_grasp);
  void SetMaxNumPointsInterfering(int max_num_points_intefering);
  void SetCropBox(float x_max, float x_min, float y_max, float y_min, float z_max, float z_min);

  float GetOrientRadius();
  float GetDistanceRadius();
  float GetAlignmentRadius();
  uint64_t GetNumSamples();
  float GetNeighborhoodRadius();
  float GetMaxGrasperAperture();
  float GetFingerWidth();
  GrasplocPC::Ptr GetInputPointCloud();
  unsigned int GetMinNumHandleInliers();
  void GetViewpoint(float& x, float& y, float& z);
  float GetMinNumPointsInGrasp();
  float GetMaxNumPointsInterfering();

  // Private functions
 private:
  GrasplocPC::Ptr Sample();

  // Point features
  boost::shared_ptr<GraspablePoints> Extra_Filtering(GraspablePoints graspablePoints);
  boost::shared_ptr<GraspablePoints> CalcPointFeatures(const GrasplocPC::ConstPtr centroids,
    const pcl::KdTreeFLANN<GrasplocPoint>* kdtree);
  void CalcEigen(const std::vector<int>* neighborhood, Eigen::Matrix3f* eigen_vectors);
  Shell FitCylindricalShell(const std::vector<int>* neighborhood, Eigen::Vector3f norm,
    Eigen::Vector3f principal_axis);

  // Clearance checking
  boost::shared_ptr<GraspablePoints> ClearanceChecking(const pcl::KdTreeFLANN<GrasplocPoint>* kdtree,
//    boost::shared_ptr<std::vector<int>> ClearanceChecking(const pcl::KdTreeFLANN<GrasplocPoint>* kdtree,
    GraspablePoints sampled_points);
  bool RobotHandClearanceCheck(GraspablePoint& check_centroid,
    std::vector<int> outer_neighborhood);

  // Handles
  boost::shared_ptr<GraspablePoints> FindHandles(boost::shared_ptr<GraspablePoints> grasp_points);
  void FindBestColinearSet(boost::shared_ptr<GraspablePoints> grasp_points,
    const std::vector<int>* gp_indices,
    std::vector<int>* inliers_max_set,
    std::vector<int>* outliers_max_set);
  void findBestColinearSet(const boost::shared_ptr<GraspablePoints> list, std::vector<int> &inliersMaxSet,
                                       std::vector<int> &outliersMaxSet);
};

#endif  // INCLUDE_GRASPLOC_H_
