begin;

drop table if exists source_packages cascade;
drop table if exists source_package_versions cascade;
drop table if exists source_package_version_installed_files cascade;
drop table if exists source_package_shared_libraries cascade;
drop table if exists source_package_shared_library_files cascade;
drop table if exists source_package_version_current_binary_packages cascade;
drop table if exists source_package_version_attributes cascade;
drop table if exists binary_packages cascade;
drop table if exists binary_package_files cascade;
drop table if exists binary_package_attributes cascade;
drop table if exists build_pipeline_stages cascade;
drop table if exists build_pipeline_stage_events cascade;
drop table if exists rootfs_images;
drop table if exists rootfs_image_contents;
drop table if exists available_rootfs_images;

commit;
