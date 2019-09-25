BEGIN;

-- Tables
create table source_packages (
	"name" varchar primary key,
	"creation_time" timestamp with time zone not null,
	"versions_modified_time" timestamp with time zone not null,
	"versions_reassured_time" timestamp with time zone not null,
	"versions_manual_hold_time" timestamp with time zone
);

create table source_package_version (
	"source_package" varchar primary key,
	"version_number" integer[],
	"creation_time" timestamp with time zone not null
);

COMMIT;
