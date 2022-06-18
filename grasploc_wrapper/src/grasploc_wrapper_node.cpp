#include "grasploc_wrapper/grasploc_wrapper.h"

int main(int argc, char **argv) {
  ros::init(argc, argv, "grasploc");
  // Once the last nh is destroyed ros is shutdown
  ros::NodeHandle nh;

  GrasplocWrapper gloc_wrap;
  gloc_wrap.Run();
  return 0;
}
