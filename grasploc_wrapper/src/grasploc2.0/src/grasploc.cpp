#include <grasploc.h>
#include "grasploc.h"


Grasploc::Grasploc(uint64_t num_samples, float neighborhood_radius,
                  float max_grasper_aperture, float finger_width,
                  float orient_radius, float distance_radius,
                  float alignment_radius,
                  unsigned int min_num_handle_inliers,
                  int min_num_points_in_grasp,
                  int max_num_points_intefering)
    : num_samples_(num_samples),
      neighborhood_radius_(neighborhood_radius),
      finger_width_(finger_width),
      orient_radius_(orient_radius),
      distance_radius_(distance_radius),
      alignment_radius_(alignment_radius),
      num_handles_(0),
      min_num_handle_inliers_(min_num_handle_inliers),
      viewpoint_(0, 0, 0),
      min_num_points_in_grasp_(min_num_points_in_grasp),
      max_num_points_intefering_(max_num_points_intefering),
      bad_point(std::numeric_limits<float>::quiet_NaN()) {
  SetMaxGrasperAperture(max_grasper_aperture);
}

/***********
 * Setters *
 ***********/
// TODO(Kevin): Add checks bounds to all setters
void Grasploc::SetNumSamples(uint64_t num_samples) {
  num_samples_ = num_samples;
}

void Grasploc::SetNeighborhoodRadius(float  neighborhood_radius) {
  neighborhood_radius_ = neighborhood_radius;
}

void Grasploc::SetMaxGrasperAperture(float max_grasper_aperture) {
  // User inputs the full width but only the half width or radius is used
//  max_grasper_aperture_ = max_grasper_aperture / 2;
    max_grasper_aperture_ = max_grasper_aperture;
}

void Grasploc::SetFingerWidth(float finger_width) {
  finger_width_ = finger_width;
}

void Grasploc::SetOrientRadius(float orient_radius) {
  orient_radius_ = orient_radius;
}

void Grasploc::SetDistanceRadius(float distance_radius) {
  distance_radius_ = distance_radius;
}

void Grasploc::SetAlignmentRadius(float alignment_radius) {
  alignment_radius_ = alignment_radius;
}

void Grasploc::SetMinNumHandleInliers(unsigned int min_num_handle_inliers) {
  min_num_handle_inliers_ = min_num_handle_inliers;
}

void Grasploc::SetViewpoint(float x, float y, float z) {
  viewpoint_ = Eigen::Vector3f(x, y, z);
}

void Grasploc::SetMinNumPointsInGrasp(int min_num_points_in_grasp) {
  min_num_points_in_grasp_ = min_num_points_in_grasp;
}

void Grasploc::SetMaxNumPointsInterfering(int max_num_points_intefering) {
  max_num_points_intefering_ = max_num_points_intefering;
}

void Grasploc::SetCropBox(float x_max, float x_min, float y_max, float y_min, float z_max, float z_min) {
    cbx_max = x_max;
    cbx_min = x_min;
    cby_max = y_max;
    cby_min = y_min;
    cbz_max = z_max;
    cbz_min = z_min;
}

/***********
 * Getters *
 ***********/
float Grasploc::GetOrientRadius() {
  return orient_radius_;
}

float Grasploc::GetDistanceRadius() {
  return distance_radius_;
}

float Grasploc::GetAlignmentRadius() {
  return alignment_radius_;
}

uint64_t Grasploc::GetNumSamples() {
  return num_samples_;
}

float Grasploc::GetNeighborhoodRadius() {
  return neighborhood_radius_;
}

float Grasploc::GetMaxGrasperAperture() {
  return max_grasper_aperture_;
}

float Grasploc::GetFingerWidth() {
  return finger_width_;
}

Grasploc::GrasplocPC::Ptr Grasploc::GetInputPointCloud() {
  return input_pc_;
}

unsigned int Grasploc::GetMinNumHandleInliers() {
  return min_num_handle_inliers_;
}

float Grasploc::GetMinNumPointsInGrasp() {
  return min_num_points_in_grasp_;
}

float Grasploc::GetMaxNumPointsInterfering() {
  return max_num_points_intefering_;
}

void Grasploc::GetViewpoint(float& x, float& y, float& z) {
  x = viewpoint_[0];
  y = viewpoint_[1];
  z = viewpoint_[2];
}

boost::shared_ptr<Grasploc::GraspablePoints> Grasploc::Run(std::string pcd_file_name,
  unsigned int num_handles) {
  GrasplocPC::Ptr cloud_raw (new GrasplocPC);
  // Load the file
  if (pcl::io::loadPCDFile<GrasplocPoint> (pcd_file_name, *cloud_raw) == -1) {
    std::string Err_msg = "Couldn't read file " + pcd_file_name + " file \n";
    PCL_ERROR(Err_msg.c_str());
  }
    std::cout << "Read the file" << std::endl;
  return Run(cloud_raw, num_handles);
}

boost::shared_ptr<Grasploc::GraspablePoints> Grasploc::Run(const GrasplocPC::ConstPtr pc,
  unsigned int num_handles) {
  // Get the number of handles to produce

  num_handles_ = num_handles;

  // Keep an internal pointer to input_pc
  GrasplocPC::Ptr cloud_filtered (new GrasplocPC);
    GrasplocPC::Ptr cloud_cropped (new GrasplocPC);
  std::vector<int> filtered_index;

    GrasplocPoint bad_point_xyz;
    bad_point_xyz.x = bad_point_xyz.y = bad_point_xyz.z = bad_point;




  int valid_points = 0;
  std::cout << "CropBox:" << cbx_min << " " << cbx_max << " " << cby_min << " "
            << cby_max << " " << cbz_min << " " << cbz_max << std::endl;
  for(int j = 0; j<pc->points.size();j++)
  {
      if (pc->points[j].x > cbx_min && pc->points[j].x < cbx_max &&
              pc->points[j].y > cby_min && pc->points[j].y < cby_max &&
              pc->points[j].z > cbz_min && pc->points[j].z < cbz_max)  //0.79 for fetch18 //0.77 for fetch7
      {
          cloud_filtered->points.push_back(pc->points[j]);
          valid_points++;

      }
      else{

          cloud_filtered->points.push_back(bad_point_xyz);

      }
  }
    std::cout << "Valid Points: " << valid_points << std::endl;


    cloud_filtered->height = pc->height;
    cloud_filtered->width = pc->width;
    cloud_filtered->header = pc->header;
    cloud_filtered->is_dense = pc->is_dense;

// filter Nan points
    pcl::removeNaNFromPointCloud(*cloud_filtered, *cloud_cropped, filtered_index);





//  input_pc_ = cloud_filtered;
    input_pc_ = cloud_cropped;
    std::cout << "Remove the NaN" << std::endl;
  // Sample pointcloud
  GrasplocPC::Ptr neighborhoodCentroids = Sample();
    std::cout << "Sample Finish" << std::endl;



  // Construct a kdtree for finding neighbours
  pcl::KdTreeFLANN<GrasplocPoint> kdtree;
  kdtree.setInputCloud(input_pc_);
//
//  // Calculate the features
//<<<<<<< HEAD
//  std::shared_ptr<GraspablePoints> graspable_points = std::make_shared<GraspablePoints>();
//=======
  boost::shared_ptr<GraspablePoints> graspable_points(new GraspablePoints);
//  graspable_points = CalcPointFeatures(neighborhoodCentroids, &kdtree);
//>>>>>>> d328bc66155f6ebbb9be1b7da9a3edbd7504bbf2

    std::cout<< "KD-tree Done" << std::endl;

  graspable_points = CalcPointFeatures(neighborhoodCentroids, &kdtree);

  std::cout<< "Feature Calculate Done" << std::endl;
    graspable_points = ClearanceChecking(&kdtree, *graspable_points.get());

    std::cout<< graspable_points->size() << std::endl;
//
//  // If user does not want graspable points grouped into handles then
//  //  return all points
  if (num_handles_ == 0) {
    return Extra_Filtering(*graspable_points.get());
  }
//
//  // Generate handles
  return Extra_Filtering(*FindHandles(graspable_points).get());
}





boost::shared_ptr<Grasploc::GraspablePoints> Grasploc::Extra_Filtering(Grasploc::GraspablePoints sample_points){
    boost::shared_ptr<GraspablePoints> graspable_points(new GraspablePoints);
    // Eigen::Vector3f z_unit(0,0,-1), x_unit(-1,0,0);
    // int count = 0;
    for(GraspablePoints::iterator it = sample_points.begin(); it < sample_points.end(); it++){
        // count++;
        // if(((it->normal_axis).dot(z_unit)/((it->normal_axis).norm())) > sqrt(3)/2 && count <= 40){

        //     //it->normal_axis(0) = -it->normal_axis(0);
        //     graspable_points->push_back(*it);



        // } else if(((it->normal_axis).dot(x_unit)/((it->normal_axis).norm())) > sqrt(3)/2 && count <= 40){

        //     it->normal_axis(0) = -it->normal_axis(0);
        //     //it->shell.centroid(0) = it->shell.centroid(0) + 0.01;
        //     graspable_points->push_back(*it);
        // }

        graspable_points->push_back(*it);

    }
    return graspable_points;
}

Grasploc::GrasplocPC::Ptr Grasploc::Sample() {
  // Use a uniform random distribution to sample the points
  pcl::RandomSample<GrasplocPoint> rand_sample_filt;
    std::cout << "create the sample" << std::endl;

    //rand_sample_filt.setSeed(1); // zheming debug use, set seed for random sample

  rand_sample_filt.setSample(num_samples_);
  rand_sample_filt.setInputCloud(input_pc_);
  GrasplocPC::Ptr filtered_pc(new GrasplocPC);
  rand_sample_filt.filter(*filtered_pc);
  return filtered_pc;
}

boost::shared_ptr<Grasploc::GraspablePoints> Grasploc::CalcPointFeatures(
  const GrasplocPC::ConstPtr centroids,
  const pcl::KdTreeFLANN<GrasplocPoint>* kdtree) {
  // Calculate normals for all points
  Eigen::Matrix3f eigen_vectors;

  boost::shared_ptr<GraspablePoints> graspable_points(new GraspablePoints);

  for (GrasplocPC::const_iterator it = centroids->begin(); it < centroids->end(); ++it) {
    GraspablePoint graspable_point;
    // Find neighbors in a sphere
    std::vector<int> neighborhood;
    std::vector<float> distance;
    kdtree->radiusSearch(*it, neighborhood_radius_, neighborhood, distance);

    // Calculate features, eigen vectors are ordered in ascending order
    CalcEigen(&neighborhood, &eigen_vectors);

    // Get principal and normal axis from Eigen Vectors
    graspable_point.principal_axis = eigen_vectors.col(2);
    graspable_point.normal_axis = eigen_vectors.col(0);
    pcl::flipNormalTowardsViewpoint(*it, viewpoint_[0], viewpoint_[1], viewpoint_[2],
      graspable_point.normal_axis);
    graspable_point.shell = FitCylindricalShell(&neighborhood,
      graspable_point.normal_axis,
      graspable_point.principal_axis);

    // Fill up a vector of features
    graspable_points->push_back(graspable_point);
  }

  // Robot hand clearance checking
  return graspable_points;
}

void Grasploc::CalcEigen(const std::vector<int>* neighborhood, Eigen::Matrix3f* eigen_vectors) {
    if (neighborhood->empty()) {
        return;
    }
    Eigen::Vector4f xyz_centroid;
    Eigen::Matrix3f covariance_matrix;
    // Estimate the XYZ centroid
    pcl::compute3DCentroid(*input_pc_, (*neighborhood), xyz_centroid);
    // Compute the 3x3 covariance matrix
    pcl::computeCovarianceMatrix(*input_pc_, (*neighborhood), xyz_centroid, covariance_matrix);
    // Get the plane normal and surface curvature
    for (int i = 0; i < 3; ++i) {
        for (int j = 0; j < 3; ++j) {
            if (!pcl_isfinite(covariance_matrix(i, j))) {
                PCL_WARN("[Grasploc::CalcEigen] Covariance matrix has NaN/Inf values!\n");
                return;
            }
        }
    }

    // Extract the eigenvalues and eigenvectors
    EIGEN_ALIGN16 Eigen::Vector3f eigen_values;
    pcl::eigen33(covariance_matrix, (*eigen_vectors), eigen_values);
}

boost::shared_ptr<Grasploc::GraspablePoints> Grasploc::ClearanceChecking(
        const pcl::KdTreeFLANN<GrasplocPoint>* kdtree,
        GraspablePoints sampled_points){
//boost::shared_ptr< std::vector<int> > Grasploc::ClearanceChecking(
//    const pcl::KdTreeFLANN<GrasplocPoint>* kdtree,
//    GraspablePoints sampled_points) {

  boost::shared_ptr<GraspablePoints> graspable_points(new GraspablePoints);

  boost::shared_ptr< std::vector<int> > clear_check_result(new std::vector<int>); // clearance check output zheming

  float outer_sample_radius = 1.5* (max_grasper_aperture_ + finger_width_); // adding 1.5 which is is the matlab version of grasploc
  std::vector<int> outer_neighborhood;
  std::vector<float> distance;

    std::cout << max_grasper_aperture_  << std::endl;
    int graspable_points_count = 1;


  for (GraspablePoints::iterator it = sampled_points.begin(); it < sampled_points.end(); ++it) {
    if (it->shell.radius < max_grasper_aperture_) {
      // Convert point type to Grasplocpoint Type to do kdtree search
      GrasplocPoint check_centroid(it->shell.centroid[0],
                                   it->shell.centroid[1],
                                   it->shell.centroid[2]);
      kdtree->radiusSearch(check_centroid, outer_sample_radius, outer_neighborhood, distance);

      if (RobotHandClearanceCheck(*it, outer_neighborhood)) {
          clear_check_result->push_back(1);            // clearance check output zheming
          //if(graspable_points_count != 280 && graspable_points_count != 634 && graspable_points_count != 714)    // clearance check output zheming
          graspable_points->push_back(*it);

      }
        else{
          clear_check_result->push_back(0);          // clearance check output zheming
      }
    }
      else{
        clear_check_result->push_back(2);   // clearance check output zheming

    }
      graspable_points_count++;
  }
  return graspable_points;
}

bool Grasploc::RobotHandClearanceCheck(GraspablePoint& check_centroid,
                                       std::vector<int> outer_neighborhood) {
  // No reason to do work if there aren't enough points to grab
  if (outer_neighborhood.size() < min_num_points_in_grasp_) return false;

  // Sort by radial distance (it is assumed that no two points will have the same radial distance)
  std::vector<float> radial_dists;
  for (std::vector<int>::const_iterator it = outer_neighborhood.begin();
      it < outer_neighborhood.end(); ++it) {
    // Translate point such that the neighbor hood center is the origin
    Eigen::Vector3f neighbor_dist(input_pc_->points[*it].x - check_centroid.shell.centroid[0],
                                  input_pc_->points[*it].y - check_centroid.shell.centroid[1],
                                  input_pc_->points[*it].z - check_centroid.shell.centroid[2]);
    // Get the perpendicular distance to the principal axis
    //  norm((I - pp^T) * d) = norm(d - dot(d, p) * p)
    float axial_dist = neighbor_dist.dot(check_centroid.principal_axis);
    float radial_dist = (neighbor_dist - axial_dist * check_centroid.principal_axis).norm();
    if(std::abs(axial_dist) < check_centroid.shell.extent){
      radial_dists.push_back(radial_dist);
    }

  }

  Eigen::VectorXf normalDist(radial_dists.size());
  for(int i = 0; i < radial_dists.size(); i++){
    normalDist(i) = radial_dists[i];
  }

  for (double r = check_centroid.shell.radius; r <= max_grasper_aperture_; r += 0.001)
  {
      int numInGap = ((normalDist.array() > r) * (normalDist.array() < r + finger_width_) == true).count();
      int numInside = (normalDist.array() <= r).count();
      //~ printf("numInGap: %i, numInside: %i, \n", numInGap, numInside);

      if (numInGap < max_num_points_intefering_ && numInside > min_num_points_in_grasp_)
      {
          check_centroid.shell.radius = r;
          return true;
      }
  }

  return false;

}

// Fit a cylindrical shell to the neighborhood
//  norm and principle axis must be unit vectors
Grasploc::Shell Grasploc::FitCylindricalShell(const std::vector<int>* neighborhood,
  Eigen::Vector3f norm, Eigen::Vector3f principal_axis) {
  // Generate rotation (as a homegenous transform) to align
  //  the norm with x axis and y with principal_axis
  //  This can also be seen as a change of basis from standard basis to
  //     b = {norm, principal_axis, norm X principal_axis}
  //  Changing the basis of the points to b and setting the component corresponding to the
  //    principal_axis to zero yields the projection onto the plane that has the
  //    principal_axis as its norm
  Eigen::Matrix4f rot = Eigen::Matrix4f::Identity();
  rot.block<1, 3>(0, 0) = norm;
  rot.block<1, 3>(1, 0) = principal_axis;
  rot.block<1, 3>(2, 0) = norm.cross(principal_axis);

  // Rotate the pointcloud to b
  GrasplocPC tfed_pc;
  pcl::transformPointCloud(*input_pc_, *neighborhood, tfed_pc, rot);


  Eigen::Matrix<float, 3, Eigen::Dynamic> pts(3, neighborhood->size());
  Eigen::Vector3f weighted_sum = Eigen::Vector3f::Zero();
  float sum_y = 0;
  float min_y = tfed_pc.points[0].y;
  float max_y = tfed_pc.points[0].y;
  double inv_error = 0;
  int i = 0;
  for (GrasplocPC::const_iterator it = tfed_pc.begin();
    it < tfed_pc.end(); ++it, ++i) {
    // Construct point
    pts.col(i)(0) = it->x;
    pts.col(i)(1) = it->z;
    pts.col(i)(2) = 1;

    // Construct sum of squares
    float sum_squares = pow(it->x, 2.0f) + pow(it->z, 2.0f);

    // Accumulate wieghted sum
    weighted_sum += sum_squares * pts.col(i);

    // Accumulate ys
    sum_y += it->y;

    // Get min and max y
    if (it->y < min_y) {
      min_y = it->y;
    } else if (it->y > max_y) {
      max_y = it->y;
    }
  }

  // Covariance like matrix of points if the mean were 0,0,0
  //  var(x), cov(x,z), 0
  //  cov(x,z), var(z), 0
  //    0,        0,  neighborhood->size()
  Eigen::Matrix3f Q = pts * pts.transpose();

  // Solve Q * params = weighted_sum
  //  Since Q will be positive semi definite by construction we can use ldlt solver
  //  which is fast for large and small matrices and accurate
  // TODO(Kevin): Explain what params are and why theres a -1
  Eigen::Vector3f params;
  params = -1 * Q.ldlt().solve(weighted_sum);
//  params = -1 * Q.partialPivLu().solve(weighted_sum);

    // FOR  MATRIX INVERSE ERROR  CHECKING
//  inv_error = (Q*params + weighted_sum).norm() / weighted_sum.norm();
//  std::cout << inv_error << std::endl;

  Shell shell;
  float avg_y = sum_y / neighborhood->size();
  Eigen::Vector3f tfed_centroid;
  tfed_centroid(0) = -0.5 * params(0);
  tfed_centroid(1) = avg_y;
  tfed_centroid(2) = -0.5 * params(1);
  shell.centroid = rot.block<3, 3>(0, 0).transpose() * tfed_centroid;
  shell.radius = sqrt(0.25 * (pow(params(0), 2) + pow(params(1), 2)) - params(2));
  shell.extent = max_y - min_y;
  shell.param = params;
  return shell;
}



boost::shared_ptr<Grasploc::GraspablePoints> Grasploc::FindHandles(
  boost::shared_ptr<GraspablePoints> grasp_points) {
  // Initilization
  boost::shared_ptr<GraspablePoints> handle_points(new GraspablePoints);
  uint64_t handle_index = 0;

  std::vector<int> gp_indices(grasp_points->size(), 0);
  for (int i = 0; i < grasp_points->size(); ++i) {gp_indices[i] = i;}
  std::vector<int> inliers_max_set;
  std::vector<int> outliers_max_set;

  for (uint64_t i = 1; (i <= num_handles_) && (gp_indices.size() > 0); i++) {
    // Find colinear graspable points indices
//    FindBestColinearSet(grasp_points, &gp_indices, &inliers_max_set, &outliers_max_set);
      findBestColinearSet(grasp_points,inliers_max_set,outliers_max_set);
    if (inliers_max_set.size() >= min_num_handle_inliers_) {
      // Save colinear graspable points
      for (std::vector<int>::const_iterator it = inliers_max_set.begin();
        it < inliers_max_set.end(); ++it) {
        grasp_points->at(*it).handle_index = handle_index;
        handle_points->push_back(grasp_points->at(*it));
        std::cout << *it << std::endl;
      }
      // Put outliers_max_set into gp_indices for next evaluation
      gp_indices = outliers_max_set;

      handle_index++;

    } else {
      // No more handles to be found inliers_max_set.size() is monotonically decreasing
      break;
    }
  }
  return handle_points;
}

void Grasploc::findBestColinearSet(const boost::shared_ptr<GraspablePoints> list, std::vector<int> &inliersMaxSet,
                                      std::vector<int> &outliersMaxSet)
{
    int maxInliers = 0;
    std::cout << orient_radius_ << " " << distance_radius_ << " " << alignment_radius_ << std::endl;

    for (std::size_t i = 0; i < list->size(); i++)
    {
        Eigen::Vector3f axis = list->at(i).principal_axis;
        Eigen::Vector3f centroid = list->at(i).shell.centroid;
        float radius = list->at(i).shell.radius;
        std::vector<int> inliers, outliers;

        for (std::size_t j = 0; j < list->size(); j++)
        {
            Eigen::Vector3f distToOrientVec = (Eigen::MatrixXf::Identity(3, 3) - axis * axis.transpose())
                                              * list->at(j).principal_axis;
            float distToOrient = distToOrientVec.cwiseProduct(distToOrientVec).sum();
            Eigen::Vector3f distToAxisVec = (Eigen::MatrixXf::Identity(3, 3) - axis * axis.transpose())
                                            * (list->at(j).shell.centroid - centroid);
            float distToAxis = distToAxisVec.cwiseProduct(distToAxisVec).sum();
            float distToRadius = fabs(list->at(j).shell.radius - radius);

            if (distToOrient < orient_radius_ && distToAxis < distance_radius_ && distToRadius < alignment_radius_)
                inliers.push_back(j);
            else
                outliers.push_back(j);
        }

        if (inliers.size() > maxInliers)
        {
            maxInliers = inliers.size();
            inliersMaxSet = inliers;
            outliersMaxSet = outliers;
        }
    }
}










