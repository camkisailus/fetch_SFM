#include <iostream>
#include <string>

#include "grasploc.h"
#include "util.h"

#include "boost/program_options.hpp"

namespace po = boost::program_options;

  void SetNumSamples(uint64_t num_samples);
  void SetNeighborhoodRadius(float  neighborhood_radius);
  void SetOrientRadius(float orient_radius);
  void SetDistanceRadius(float distance_radius);
  void SetAlignmentRadius(float alignment_radius);
  void SetMinNumHandleInliers(unsigned int min_num_handle_inliers);

int main(int argc, char** argv) {
  // Setup variables to hold values of command line args
  uint64_t num_samples;
  float  neighborhood_radius;
  float orient_radius;
  float distance_radius;
  float alignment_radius;
  unsigned int min_num_handle_inliers;
  std::string file;
  unsigned int number_of_handles;
  float vx, vy, vz;
  float cb_x_max, cb_x_min, cb_y_max, cb_y_min, cb_z_max, cb_z_min;
  int min_num_points_in_grasp;
  int max_num_points_intefering;
  float max_grasper_aperture;
  float finger_width;

  // Initilise the geometry class
  Grasploc g_p;

  // Define command line args
  po::options_description desc("Allowed options");
  desc.add_options()
    ("help,h", "Show this help message")

    ("num_samples,n", po::value<uint64_t>(&num_samples)->default_value(2000),
      "Number of points to sample from point cloud")

    ("neighborhood_radius", po::value<float>(&neighborhood_radius)->default_value(0.025),
      "Radius of nearest neighbours search")

    ("orient_radius", po::value<float>(&orient_radius)->default_value(0.09),
      "Orientation radius for handle calculation")

    ("distance_radius", po::value<float>(&distance_radius)->default_value(0.0016),
      "Distance radius for handle calculation")

    ("alignment_radius", po::value<float>(&alignment_radius)->default_value(0.01),
      "Alignment radius for handle calculation")

    ("min_num_handle_inliers", po::value<unsigned int>(&min_num_handle_inliers)->default_value(4),
      "Minimum number of inliers required to form a handle")

    ("file,f", po::value<std::string>(&file)->required(),
      "Name of file to process, a file must be supplied")

    ("number_of_handles,l", po::value<unsigned int>(&number_of_handles)->default_value(1),
      "Number of handles to find, 0 means just return all points without forming handles")

    ("viewpoint_x,x", po::value<float>(&vx)->default_value(0),
      "The x position of the viewpoint that all normals are oriented towards")

    ("viewpoint_y,y", po::value<float>(&vy)->default_value(0),
      "The y position of the viewpoint that all normals are oriented towards")

    ("viewpoint_z,z", po::value<float>(&vz)->default_value(0),
      "The z position of the viewpoint that all normals are oriented towards")

    ("cropbox_x_min,x_min", po::value<float>(&cb_x_min)->default_value(0),
    "The cropbox x min for cropping the point cloud")

    ("cropbox_x_max,x_max", po::value<float>(&cb_x_max)->default_value(1),
     "The cropbox x max for cropping the point cloud")

    ("cropbox_y_min,y_min", po::value<float>(&cb_y_min)->default_value(-0.41),
     "The cropbox y min for cropping the point cloud")

    ("cropbox_y_max,y_max", po::value<float>(&cb_y_max)->default_value(0.4),
      "The cropbox y max for cropping the point cloud")

    ("cropbox_z_min,z_min", po::value<float>(&cb_z_min)->default_value(0.6),
      "The cropbox z min for cropping the point cloud")

    ("cropbox_z_max,z_max", po::value<float>(&cb_z_max)->default_value(1.2),
      "The cropbox z max for cropping the point cloud")

    ("min_num_points_in_grasp", po::value<int>(&min_num_points_in_grasp)->default_value(40),
      "The minimum number of points that are required to be inside of a grasp")

    ("max_num_points_intefering", po::value<int>(&max_num_points_intefering)->default_value(5),
      "The maximum number of points allowed to interfere with the gripper")

    ("max_grasper_aperture", po::value<float>(&max_grasper_aperture)->default_value(0.055),
      "The maximum empty space between the two sides of the gripper")

    ("finger_width", po::value<float>(&finger_width)->default_value(0.01),
      "Size of one of the two symetric fingers on either side of the gripper");

  try {
    // Parse command line args
    po::variables_map vm;
    po::store(po::parse_command_line(argc, argv, desc), vm);

    // Process help
    if (vm.count("help")) {
      std::cout << desc << "\n";
      return 0;
    }

    // Raise errors
    po::notify(vm);
  } catch (po::error& e) {
    std::cout << e.what() << "\n" << desc << "\n";
    return 0;
  }

  // Set algorithm params from cmd line
  g_p.SetNumSamples(num_samples);
  g_p.SetNeighborhoodRadius(neighborhood_radius);
  g_p.SetOrientRadius(orient_radius);
  g_p.SetDistanceRadius(distance_radius);
  g_p.SetAlignmentRadius(alignment_radius);
  g_p.SetMinNumHandleInliers(min_num_handle_inliers);
  g_p.SetViewpoint(vx, vy, vz);
  g_p.SetMinNumPointsInGrasp(min_num_points_in_grasp);
  g_p.SetMaxNumPointsInterfering(max_num_points_intefering);
  g_p.SetMaxGrasperAperture(max_grasper_aperture);
  g_p.SetFingerWidth(finger_width);
  g_p.SetCropBox(cb_x_max, cb_x_min, cb_y_max, cb_y_min, cb_z_max, cb_z_min);

  boost::shared_ptr<Grasploc::GraspablePoints> vis_pc = g_p.Run(file, number_of_handles);
    std::cout << vis_pc->size() << std::endl;


  boost::shared_ptr<pcl::visualization::PCLVisualizer> viewer;
  simpleVis(viewer, *vis_pc.get(), g_p.GetInputPointCloud());

  while (!viewer->wasStopped()) {
    viewer->spinOnce(100);
    boost::this_thread::sleep(boost::posix_time::microseconds(100000));

  }
}
