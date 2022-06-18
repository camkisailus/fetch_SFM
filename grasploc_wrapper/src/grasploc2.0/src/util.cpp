#include "util.h"

void simpleVis(
  boost::shared_ptr<pcl::visualization::PCLVisualizer>& viewer,
  const Grasploc::GraspablePoints& cloud,
  const pcl::PointCloud<pcl::PointXYZ>::Ptr& raw_cloud) {
  // --------------------------------------------
  // -----Open 3D viewer and add point cloud-----
  // --------------------------------------------
  pcl::PointCloud<pcl::PointXYZ>::Ptr normal_axis_pc(new pcl::PointCloud<pcl::PointXYZ>);
  pcl::PointCloud<pcl::PointXYZ>::Ptr principal_axis_pc(new pcl::PointCloud<pcl::PointXYZ>);
  pcl::PointCloud<pcl::PointXYZ>::Ptr shell_centroid_pc(new pcl::PointCloud<pcl::PointXYZ>);



  double scalar(0.1);
  for (size_t i = 0; i < cloud.size(); i++) {
    // Insert sampled point clouds
    shell_centroid_pc->push_back(pcl::PointXYZ(cloud[i].shell.centroid[0],
                                               cloud[i].shell.centroid[1],
                                               cloud[i].shell.centroid[2]));
    // Insert normal axis
    pcl::PointXYZ normal_axis = pcl::PointXYZ(
        cloud[i].shell.centroid[0] + scalar*cloud[i].normal_axis[0],
        cloud[i].shell.centroid[1] + scalar*cloud[i].normal_axis[1],
        cloud[i].shell.centroid[2] + scalar*cloud[i].normal_axis[2]);

    normal_axis_pc->push_back(normal_axis);
    // Insert principle axis
    pcl::PointXYZ principal_axis = pcl::PointXYZ(
        cloud[i].shell.centroid[0] + scalar*cloud[i].principal_axis[0],
        cloud[i].shell.centroid[1] + scalar*cloud[i].principal_axis[1],
        cloud[i].shell.centroid[2] + scalar*cloud[i].principal_axis[2]);

    principal_axis_pc->push_back(principal_axis);
  }

  // Check if viewer already exist
  if (viewer) {
    // Viewer exist so just clear the old data
    viewer->removeAllPointClouds();
    viewer->removeAllShapes();
    viewer->removeCoordinateSystem();
  } else {
    // Viewer does not exist so create it
    viewer = boost::shared_ptr<pcl::visualization::PCLVisualizer> (
      new pcl::visualization::PCLVisualizer ("3D Viewer"));
  }

  viewer->setBackgroundColor(0, 0, 0);
  // Visualize sampled point clouds
  pcl::visualization::PointCloudColorHandlerCustom<pcl::PointXYZ> single_color(
      shell_centroid_pc, 0, 255, 0);
  viewer->addPointCloud<pcl::PointXYZ>(shell_centroid_pc, single_color, "sample cloud");
  viewer->setPointCloudRenderingProperties(
      pcl::visualization::PCL_VISUALIZER_POINT_SIZE,
      5, "sample cloud");
  // Visualize raw point clouds
  pcl::visualization::PointCloudColorHandlerCustom<pcl::PointXYZ> single_raw_color(
      raw_cloud,
      168, 111, 247);
  viewer->addPointCloud<pcl::PointXYZ>(raw_cloud, single_raw_color, "raw cloud");
  viewer->setPointCloudRenderingProperties(
      pcl::visualization::PCL_VISUALIZER_POINT_SIZE,
      1, "raw cloud");

  for (size_t i = 0; i < cloud.size(); i++) {
    // Convert i to a string
    std::string i_str = static_cast<std::ostringstream*>( &(std::ostringstream() << i) )->str();

    // Visualize normal_axis
    viewer->addLine<pcl::PointXYZ>(
        shell_centroid_pc->points[i], normal_axis_pc->points[i],
        0, 0, 225,
        "normal_axis_" + i_str);
    // Visualize principal_axis
    viewer->addLine<pcl::PointXYZ>(
        shell_centroid_pc->points[i],
        principal_axis_pc->points[i],
        225, 0, 0,
        "principal_axis_" + i_str);

    // Visualize curvature with cylinder
    float height = cloud[i].shell.extent;
    Eigen::Vector3f offset_centroid =
      cloud[i].shell.centroid - cloud[i].principal_axis * (height / 2);
    Eigen::Vector3f axis = cloud[i].principal_axis * height;
    pcl::ModelCoefficients coeffs;
    coeffs.values.resize(7);
    // Point on axis
    coeffs.values[0] = offset_centroid[0];  // x
    coeffs.values[1] = offset_centroid[1];  // y
    coeffs.values[2] = offset_centroid[2];  // z
    // Axis direction
    coeffs.values[3] = axis[0];  // x
    coeffs.values[4] = axis[1];  // y
    coeffs.values[5] = axis[2];  // z
    // Radius
    coeffs.values[6] = cloud[i].shell.radius;
    // Add to view
    viewer->addCylinder(coeffs, "curvature_" + i_str);
  }

  viewer->addCoordinateSystem(1.0);
  viewer->initCameraParameters();

}

