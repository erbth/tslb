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
	"creation_time" timestamp with time zone not null,
	primary key("source_package", "version_number")
);

COMMIT;
