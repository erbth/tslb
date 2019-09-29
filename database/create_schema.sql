BEGIN;

-- Tables
create table source_packages (
	"name" varchar primary key,
	"creation_time" timestamp with time zone not null,
	"versions_modified_time" timestamp with time zone not null,
	"versions_reassured_time" timestamp with time zone not null,
	"versions_manual_hold_time" timestamp with time zone
);

create table source_package_versions (
	"source_package" varchar references source_packages on update cascade on delete cascade,
	"version_number" integer[],
	primary key("source_package", "version_number"),

	"creation_time" timestamp with time zone not null,

	files_modified_time timestamp with time zone not null,
	files_reassured_time timestamp with time zone not null
);

create table source_package_version_files (
	source_package varchar,
	source_package_version_number integer[],
	foreign key (source_package, source_package_version_number)
		references source_package_versions(source_package, version_number)
		on update cascade on delete cascade,

	"path" varchar not null,
	"sha512sum" varchar not null,

	primary key(source_package, source_package_version_number, "path")
);

create table source_package_version_attributes (
	source_package varchar,
	version_number integer[],
	foreign key (source_package, version_number)
		references source_package_versions(source_package, version_number)
		on update cascade on delete cascade,

	modified_time timestamp with time zone not null,
	reassured_time timestamp with time zone not null,
	manual_hold_time timestamp with time zone,

	"key" varchar,
	"value" varchar,

	primary key (source_package, version_number, "key")
);

COMMIT;
