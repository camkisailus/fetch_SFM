#ifndef INCLUDE_UTIL_H_
#define INCLUDE_UTIL_H_
// util for visualization
#include <boost/thread/thread.hpp>
#include <pcl/common/common_headers.h>
#include <pcl/features/normal_3d.h>
#include <pcl/io/pcd_io.h>
#include <pcl/visualization/pcl_visualizer.h>
#include <pcl/console/parse.h>

#include <iostream>
#include <sstream>
#include <string>

#include "grasploc.h"

void simpleVis(
  boost::shared_ptr<pcl::visualization::PCLVisualizer>& viewer,
  const Grasploc::GraspablePoints& cloud,
  const pcl::PointCloud<pcl::PointXYZ>::Ptr& raw_cloud);

#endif  // INCLUDE_UTIL_H_
