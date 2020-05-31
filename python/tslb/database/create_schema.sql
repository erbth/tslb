BEGIN;

-- Tables
-- Source packages and related stuff
create table source_packages (
	"name" varchar,
	"architecture" integer,
	primary key ("name", "architecture"),

	"creation_time" timestamp with time zone not null,
	"versions_modified_time" timestamp with time zone not null,
	"versions_reassured_time" timestamp with time zone not null,
	"versions_manual_hold_time" timestamp with time zone
);

create table source_package_versions (
	"source_package" varchar,
	"architecture" integer,
	foreign key ("source_package", "architecture")
		references source_packages("name", "architecture")
		on update cascade on delete cascade,

	"version_number" integer[],
	primary key("source_package", "architecture", "version_number"),

	"creation_time" timestamp with time zone not null,

	installed_files_modified_time timestamp with time zone not null,
	installed_files_reassured_time timestamp with time zone not null,

	current_binary_packages_modified_time timestamp with time zone not null,
	current_binary_packages_reassured_time timestamp with time zone not null
);

create table source_package_version_installed_files (
	source_package varchar,
	"architecture" integer,
	version_number integer[],
	foreign key (source_package, "architecture", version_number)
		references source_package_versions(source_package, "architecture", version_number)
		on update cascade on delete cascade,

	"path" varchar not null,
	"sha512sum" varchar,

	primary key(source_package, "architecture", version_number, "path")
);

create table source_package_shared_libraries (
	source_package varchar,
	"architecture" integer,
	source_package_version_number integer[],

	name varchar,
	version_number integer[],
	abi_version_number integer[],
	soname varchar,
	"id" bigserial not null unique,

	foreign key (source_package, "architecture", source_package_version_number)
		references source_package_versions(source_package, "architecture", version_number)
		on update cascade on delete cascade,

	primary key (source_package, "architecture", source_package_version_number,
		name, soname)
);

create table source_package_shared_library_files (
	source_package_id bigint
		references source_package_shared_libraries("id") on update cascade on delete cascade,
	"path" varchar,
	"is_dev_symlink" boolean not null,

	primary key(source_package_id, "path")
);

-- Source packages' current binary packages
create table source_package_version_current_binary_packages (
	source_package varchar,
	"architecture" integer,
	version_number integer[],
	foreign key (source_package, "architecture", version_number)
		references source_package_versions(source_package, "architecture", version_number)
		on update cascade on delete cascade,

	name varchar,
	primary key (architecture, name)
);

create table source_package_version_attributes (
	source_package varchar,
	"architecture" integer,
	version_number integer[],
	foreign key (source_package, "architecture", version_number)
		references source_package_versions(source_package, "architecture", version_number)
		on update cascade on delete cascade,

	modified_time timestamp with time zone not null,
	reassured_time timestamp with time zone not null,
	manual_hold_time timestamp with time zone,

	"key" varchar,
	"value" varchar,

	primary key (source_package, "architecture", version_number, "key")
);

-- Binary packages
create table binary_packages (
	source_package varchar,
	"architecture" integer,
	source_package_version_number integer[],
	foreign key(source_package, "architecture", source_package_version_number)
		references source_package_versions (source_package, "architecture", version_number)
		on update cascade on delete cascade,

	name varchar,
	version_number integer[],
	primary key (name, "architecture", version_number),

	creation_time timestamp with time zone not null,

	-- Files
	files_modified_time timestamp with time zone not null,
	files_reassured_time timestamp with time zone not null
);

create table binary_package_files (
	binary_package varchar,
	"architecture" integer,
	version_number integer[],
	foreign key (binary_package, "architecture", version_number)
		references binary_packages(name, "architecture", version_number)
		on update cascade on delete cascade,

	"path" varchar not null,
	"sha512sum" varchar,

	primary key(binary_package, "architecture", version_number, "path")
);

create table binary_package_attributes (
	binary_package varchar,
	"architecture" integer,
	version_number integer[],
	foreign key (binary_package, "architecture", version_number)
		references binary_packages(name, "architecture", version_number)
		on update cascade on delete cascade,

	modified_time timestamp with time zone not null,
	reassured_time timestamp with time zone not null,
	manual_hold_time timestamp with time zone,

	"key" varchar,
	"value" varchar,

	primary key (binary_package, "architecture", version_number, "key")
);

-- The build pipeline
create table build_pipeline_stages (
	name varchar primary key,
	parent varchar not null
);

create table build_pipeline_stage_events (
	stage varchar references build_pipeline_stages,
	time timestamp with time zone,

	source_package varchar,
	"architecture" integer,
	version_number integer[],
	foreign key (source_package, "architecture", version_number) references
		source_package_versions (source_package, "architecture", version_number)
		on update cascade on delete cascade,

	status integer not null,
	output varchar,

	snapshot_path varchar,
	snapshot_name varchar,

	primary key (stage, time, source_package, "architecture", version_number)
);

-- Root filesystems
create table rootfs_images (
	id bigserial primary key,
	"comment" varchar
);

create table rootfs_image_contents (
	id bigint references rootfs_images on update cascade on delete cascade,
	package varchar,
	version integer[],
	arch integer,

	primary key (id, package, version, arch)
);

create table available_rootfs_images (
	id bigint primary key references rootfs_images
);

create index on rootfs_image_contents (
	package,
	version,
	arch
);

COMMIT;
