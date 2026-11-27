--
-- PostgreSQL database dump
--

-- Dumped from database version 16.4 (Debian 16.4-1.pgdg110+2)
-- Dumped by pg_dump version 16.4 (Debian 16.4-1.pgdg110+2)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: tiger; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA tiger;


--
-- Name: tiger_data; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA tiger_data;


--
-- Name: topology; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA topology;


--
-- Name: SCHEMA topology; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA topology IS 'PostGIS Topology schema';


--
-- Name: fuzzystrmatch; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS fuzzystrmatch WITH SCHEMA public;


--
-- Name: EXTENSION fuzzystrmatch; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION fuzzystrmatch IS 'determine similarities and distance between strings';


--
-- Name: postgis; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS postgis WITH SCHEMA public;


--
-- Name: EXTENSION postgis; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION postgis IS 'PostGIS geometry and geography spatial types and functions';


--
-- Name: postgis_tiger_geocoder; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS postgis_tiger_geocoder WITH SCHEMA tiger;


--
-- Name: EXTENSION postgis_tiger_geocoder; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION postgis_tiger_geocoder IS 'PostGIS tiger geocoder and reverse geocoder';


--
-- Name: postgis_topology; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS postgis_topology WITH SCHEMA topology;


--
-- Name: EXTENSION postgis_topology; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION postgis_topology IS 'PostGIS topology spatial types and functions';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: audit_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_logs (
    actor_id character varying(36),
    action character varying(64) NOT NULL,
    entity_type character varying(64) NOT NULL,
    entity_id character varying(64),
    before json,
    after json,
    ip character varying(64),
    ua character varying(255),
    id character varying(36) NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: campus_reports; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.campus_reports (
    campus_id character varying(36) NOT NULL,
    location_id character varying(36),
    category character varying(48) NOT NULL,
    status character varying(16) NOT NULL,
    description character varying(500),
    image_key character varying(255),
    reported_by character varying(36),
    reported_at timestamp with time zone NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    confidence character varying(16) NOT NULL,
    confirmation_count integer NOT NULL,
    disagreement_count integer NOT NULL,
    flag_count integer NOT NULL,
    moderation_status character varying(16) NOT NULL,
    id character varying(36) NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: campuses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.campuses (
    university_id character varying(36) NOT NULL,
    slug character varying(64) NOT NULL,
    name character varying(160) NOT NULL,
    id character varying(36) NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    lat double precision,
    lng double precision
);


--
-- Name: departments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.departments (
    faculty_id character varying(36) NOT NULL,
    name character varying(160) NOT NULL,
    code character varying(24),
    id character varying(36) NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: faculties; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.faculties (
    campus_id character varying(36) NOT NULL,
    name character varying(160) NOT NULL,
    code character varying(24),
    id character varying(36) NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: levels; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.levels (
    programme_id character varying(36) NOT NULL,
    name character varying(32) NOT NULL,
    rank integer NOT NULL,
    id character varying(36) NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: location_suggestions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.location_suggestions (
    campus_id character varying(36) NOT NULL,
    proposed_by character varying(36),
    name character varying(160) NOT NULL,
    category character varying(32) NOT NULL,
    description character varying(500),
    lat double precision NOT NULL,
    lng double precision NOT NULL,
    status character varying(16) NOT NULL,
    moderated_by character varying(36),
    moderated_at timestamp with time zone,
    moderation_note character varying(255),
    approved_location_id character varying(36),
    id character varying(36) NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: locations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.locations (
    campus_id character varying(36) NOT NULL,
    name character varying(160) NOT NULL,
    category character varying(32) NOT NULL,
    description character varying(500),
    point public.geometry(Point,4326) NOT NULL,
    polygon public.geometry(Polygon,4326),
    opening_hours character varying(120),
    phone character varying(32),
    source character varying(16) NOT NULL,
    status character varying(16) NOT NULL,
    created_by character varying(36),
    verified_by character varying(36),
    verified_at timestamp with time zone,
    id character varying(36) NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: notifications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notifications (
    recipient_id character varying(36) NOT NULL,
    type character varying(48) NOT NULL,
    title character varying(160) NOT NULL,
    body character varying(500),
    action_url character varying(255),
    campus_id character varying(36),
    related_entity_type character varying(32),
    related_entity_id character varying(36),
    dedupe_key character varying(255),
    read_at timestamp with time zone,
    dismissed_at timestamp with time zone,
    expires_at timestamp with time zone,
    id character varying(36) NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: programmes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.programmes (
    department_id character varying(36) NOT NULL,
    name character varying(160) NOT NULL,
    code character varying(24),
    id character varying(36) NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: push_subscriptions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.push_subscriptions (
    user_id character varying(36) NOT NULL,
    endpoint text NOT NULL,
    p256dh character varying(255) NOT NULL,
    auth character varying(64) NOT NULL,
    user_agent character varying(255),
    last_success_at timestamp with time zone,
    id character varying(36) NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: report_confirmations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.report_confirmations (
    report_id character varying(36) NOT NULL,
    user_id character varying(36) NOT NULL,
    kind character varying(16) NOT NULL,
    id character varying(36) NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: report_flags; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.report_flags (
    report_id character varying(36) NOT NULL,
    user_id character varying(36),
    reason character varying(120),
    id character varying(36) NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: student_profiles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.student_profiles (
    user_id character varying(36) NOT NULL,
    university_id character varying(36) NOT NULL,
    campus_id character varying(36),
    faculty_id character varying(36),
    department_id character varying(36),
    programme_id character varying(36),
    level_id character varying(36),
    matric_no character varying(32),
    avatar_key character varying(255),
    id character varying(36) NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: tasks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tasks (
    user_id character varying(36) NOT NULL,
    title character varying(160) NOT NULL,
    description character varying(1000),
    due_at date,
    priority character varying(16) NOT NULL,
    completed_at timestamp with time zone,
    id character varying(36) NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: trust_scores; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.trust_scores (
    user_id character varying(36) NOT NULL,
    score integer NOT NULL,
    tier character varying(24) NOT NULL,
    accurate_reports integer NOT NULL,
    false_reports integer NOT NULL,
    confirmations_given integer NOT NULL,
    confirmations_received integer NOT NULL,
    abuse_flags integer NOT NULL,
    id character varying(36) NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: universities; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.universities (
    slug character varying(64) NOT NULL,
    name character varying(160) NOT NULL,
    short_name character varying(32) NOT NULL,
    state character varying(64),
    logo_key character varying(255),
    is_active boolean NOT NULL,
    id character varying(36) NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: user_sessions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_sessions (
    user_id character varying(36) NOT NULL,
    token_hash character varying(128) NOT NULL,
    ip character varying(64),
    user_agent character varying(255),
    revoked_at timestamp with time zone,
    id character varying(36) NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    email character varying(255) NOT NULL,
    phone character varying(32),
    password_hash character varying(255) NOT NULL,
    display_name character varying(80) NOT NULL,
    role character varying(32) NOT NULL,
    status character varying(24) NOT NULL,
    email_verified_at timestamp with time zone,
    last_login_at timestamp with time zone,
    id character varying(36) NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Data for Name: alembic_version; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.alembic_version (version_num) FROM stdin;
6ab20090eaa4
\.


--
-- Data for Name: audit_logs; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.audit_logs (actor_id, action, entity_type, entity_id, before, after, ip, ua, id, created_at, updated_at) FROM stdin;
e6157dcc-4aad-4473-aa9a-11929c07dab8	user.register	user	e6157dcc-4aad-4473-aa9a-11929c07dab8	null	null	\N	\N	026f250a-f455-4432-97db-4a75e2e25fb1	2026-10-07 12:25:24.633751+00	2026-10-07 12:25:24.633756+00
b680416d-3b86-4bd2-acef-3abe5f0695e7	user.register	user	b680416d-3b86-4bd2-acef-3abe5f0695e7	null	null	\N	\N	9316e550-27bf-432f-b4b7-5bdb35998e81	2026-10-07 14:54:23.666353+00	2026-10-07 14:54:23.666371+00
4183fb5f-a399-4f53-ae19-907342a54338	user.suspend	user	46215433-cb2b-4ba9-9e7b-983753164135	{"status": "active"}	{"status": "suspended"}	\N	\N	2157da2a-7075-467f-9046-7327d30a5597	2026-10-09 16:15:17.4657+00	2026-10-09 16:15:17.4657+00
4183fb5f-a399-4f53-ae19-907342a54338	user.restore	user	46215433-cb2b-4ba9-9e7b-983753164135	{"status": "suspended"}	{"status": "active"}	\N	\N	5b3aa716-9934-4ad8-b244-25368c614911	2026-10-09 16:15:27.582331+00	2026-10-09 16:15:27.582331+00
4183fb5f-a399-4f53-ae19-907342a54338	pulse.hide	campus_report	ec98457a-14b6-4e1d-b7f3-1dd44e2a91a5	{"moderation_status": "visible", "status": "active"}	{"moderation_status": "hidden", "status": "active"}	\N	\N	ab0abcac-4b4c-46f6-82dc-cf6c7c9df3a4	2026-10-10 19:14:43.324936+00	2026-10-10 19:14:43.324936+00
4183fb5f-a399-4f53-ae19-907342a54338	pulse.restore	campus_report	ec98457a-14b6-4e1d-b7f3-1dd44e2a91a5	{"moderation_status": "hidden", "status": "active"}	{"moderation_status": "visible", "status": "active"}	\N	\N	57e3fc89-d7da-49b0-8c39-6bb203263c7f	2026-10-10 19:20:10.391547+00	2026-10-10 19:20:10.391547+00
e8c377ea-6610-4a3c-89da-0c335392e81d	user.register	user	e8c377ea-6610-4a3c-89da-0c335392e81d	null	null	\N	\N	22fbded9-9019-4c9c-9b31-4058c4553aee	2026-10-19 15:54:44.66633+00	2026-10-19 15:54:44.666335+00
2243ab6b-d49a-4336-a201-cb367907ed2a	user.register	user	2243ab6b-d49a-4336-a201-cb367907ed2a	null	null	\N	\N	59f14089-f99a-4a09-aab2-62525624ebd0	2026-10-21 10:46:26.616786+00	2026-10-21 10:46:26.616795+00
fa1fd0e2-9feb-43b7-a3ae-6ddda7d8554f	user.register	user	fa1fd0e2-9feb-43b7-a3ae-6ddda7d8554f	null	null	\N	\N	6d70bf25-2748-4adc-8745-d332b499a7b0	2026-10-21 11:04:43.323126+00	2026-10-21 11:04:43.323131+00
2fb62d99-cda9-4482-8714-29ccf811eb5f	user.register	user	2fb62d99-cda9-4482-8714-29ccf811eb5f	null	null	\N	\N	83ebe1ee-d26b-4660-bb58-72cfdeec257c	2026-10-21 12:04:19.479043+00	2026-10-21 12:04:19.479047+00
559e1712-5b45-4c65-9752-5bb945211d83	user.register	user	559e1712-5b45-4c65-9752-5bb945211d83	null	null	\N	\N	f8a368dd-69c9-496c-9b0f-2a1f9eb7140a	2026-10-24 14:51:12.284761+00	2026-10-24 14:51:12.284768+00
7016bb1f-9789-48f1-a860-bd13640996bb	user.register	user	7016bb1f-9789-48f1-a860-bd13640996bb	null	null	\N	\N	3225b584-27f2-47a9-826b-1d59de28a267	2026-10-24 16:33:04.055049+00	2026-10-24 16:33:04.055075+00
da0b04e5-86e5-459a-9f36-72ce59b629e2	user.register	user	da0b04e5-86e5-459a-9f36-72ce59b629e2	null	null	\N	\N	d936226c-3fba-4f7c-b8e5-ad836c420e55	2026-10-24 16:48:18.447282+00	2026-10-24 16:48:18.447292+00
8c851607-350e-4177-8ea5-da9506c0fbc3	user.register	user	8c851607-350e-4177-8ea5-da9506c0fbc3	null	null	\N	\N	7e81c3ae-40ec-4627-afd5-494f92abb322	2026-10-26 11:02:05.660507+00	2026-10-26 11:02:05.660512+00
5ec88c7c-c351-4e95-b990-79d9afcb0bd2	user.register	user	5ec88c7c-c351-4e95-b990-79d9afcb0bd2	null	null	\N	\N	aed8a9cb-713b-42c3-a27e-e1a4165f4b3c	2026-11-21 14:37:36.664152+00	2026-11-21 14:37:36.664164+00
\.


--
-- Data for Name: campus_reports; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.campus_reports (campus_id, location_id, category, status, description, image_key, reported_by, reported_at, expires_at, confidence, confirmation_count, disagreement_count, flag_count, moderation_status, id, created_at, updated_at) FROM stdin;
47f17cfd-6a85-4f74-9ec9-c587dc44c918	\N	traffic_clear	active	The road is now clear	\N	e6157dcc-4aad-4473-aa9a-11929c07dab8	2026-10-10 15:57:21.499623+00	2026-10-10 16:27:21.498108+00	low	0	0	0	visible	a2657c18-fbc5-4f14-98ff-f4b2b0840f3b	2026-10-10 15:57:21.499623+00	2026-10-10 15:57:21.499623+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	\N	power_outage	active	\N	\N	b680416d-3b86-4bd2-acef-3abe5f0695e7	2026-10-10 18:00:41.451664+00	2026-10-10 19:30:41.451664+00	low	0	0	0	visible	a8ea83ff-fe64-4a58-964b-249034f8c51f	2026-10-10 18:00:41.454196+00	2026-10-10 18:00:41.454196+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	\N	flooding	active	\N	\N	b680416d-3b86-4bd2-acef-3abe5f0695e7	2026-10-10 18:00:41.451664+00	2026-10-10 21:00:41.451664+00	low	0	0	3	visible	e0be89bd-3f7d-49cb-9f49-f3727d1c3d6a	2026-10-10 18:00:41.462881+00	2026-10-10 18:00:41.462881+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	\N	power_outage	active	\N	\N	b680416d-3b86-4bd2-acef-3abe5f0695e7	2026-10-10 18:01:01.108831+00	2026-10-10 19:31:01.108831+00	low	0	0	0	visible	ce613e52-ef11-410f-9d1f-d8633f5e4203	2026-10-10 18:01:01.114719+00	2026-10-10 18:01:01.114719+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	\N	power_outage	active	\N	\N	b680416d-3b86-4bd2-acef-3abe5f0695e7	2026-10-10 18:01:01.108831+00	2026-10-10 19:31:01.108831+00	low	0	0	0	visible	36620fea-12d7-4e24-83e3-8b7d9700c163	2026-10-10 18:01:01.114719+00	2026-10-10 18:01:01.114719+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	\N	power_outage	active	\N	\N	b680416d-3b86-4bd2-acef-3abe5f0695e7	2026-10-10 18:01:01.108831+00	2026-10-10 19:31:01.108831+00	low	0	0	0	visible	be0882aa-c921-4806-a3e7-bfd4da65ae97	2026-10-10 18:01:01.114719+00	2026-10-10 18:01:01.114719+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	\N	power_outage	active	\N	\N	b680416d-3b86-4bd2-acef-3abe5f0695e7	2026-10-10 18:01:01.108831+00	2026-10-10 19:31:01.108831+00	low	0	0	0	visible	781281f1-34df-4f9b-8be6-8226a689049c	2026-10-10 18:01:01.114719+00	2026-10-10 18:01:01.114719+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	\N	power_outage	active	\N	\N	b680416d-3b86-4bd2-acef-3abe5f0695e7	2026-10-10 18:01:01.108831+00	2026-10-10 19:31:01.108831+00	low	0	0	0	visible	bff983ac-e155-4f35-b4d7-157f6775ffac	2026-10-10 18:01:01.114719+00	2026-10-10 18:01:01.114719+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	\N	power_outage	active	\N	\N	b680416d-3b86-4bd2-acef-3abe5f0695e7	2026-10-10 18:01:01.108831+00	2026-10-10 19:31:01.108831+00	low	0	0	0	visible	3ae1b86f-1623-4284-a8db-a13e56fe675e	2026-10-10 18:01:01.114719+00	2026-10-10 18:01:01.114719+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	\N	power_outage	active	\N	\N	b680416d-3b86-4bd2-acef-3abe5f0695e7	2026-10-10 18:01:01.108831+00	2026-10-10 19:31:01.108831+00	low	0	0	0	visible	c68724f7-ce48-4c43-8dea-23b5b9e71cf6	2026-10-10 18:01:01.114719+00	2026-10-10 18:01:01.114719+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	\N	power_outage	active	\N	\N	b680416d-3b86-4bd2-acef-3abe5f0695e7	2026-10-10 18:01:01.108831+00	2026-10-10 19:31:01.108831+00	low	0	0	0	visible	62b9d626-880c-4920-b944-e76d4211d60c	2026-10-10 18:01:01.114719+00	2026-10-10 18:01:01.114719+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	\N	power_outage	active	\N	\N	b680416d-3b86-4bd2-acef-3abe5f0695e7	2026-10-10 18:01:01.108831+00	2026-10-10 19:31:01.108831+00	low	0	0	0	visible	93661834-8b25-4bcd-bf5e-a9575b89ec5a	2026-10-10 18:01:01.114719+00	2026-10-10 18:01:01.114719+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	\N	power_outage	active	\N	\N	b680416d-3b86-4bd2-acef-3abe5f0695e7	2026-10-10 18:01:01.108831+00	2026-10-10 19:31:01.108831+00	low	0	0	0	visible	0bfd1946-4acd-4115-a987-0dc7abdae66e	2026-10-10 18:01:01.114719+00	2026-10-10 18:01:01.114719+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	\N	power_outage	active	\N	\N	b680416d-3b86-4bd2-acef-3abe5f0695e7	2026-10-10 18:01:01.108831+00	2026-10-10 19:31:01.108831+00	low	0	0	0	visible	8044ed98-b6ac-4992-80c0-155eb90ea324	2026-10-10 18:01:01.114719+00	2026-10-10 18:01:01.114719+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	\N	power_outage	active	\N	\N	b680416d-3b86-4bd2-acef-3abe5f0695e7	2026-10-10 18:01:01.108831+00	2026-10-10 19:31:01.108831+00	low	0	0	0	visible	81e5cc83-6aab-4ea6-8867-be23315f27af	2026-10-10 18:01:01.114719+00	2026-10-10 18:01:01.114719+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	\N	power_outage	active	\N	\N	b680416d-3b86-4bd2-acef-3abe5f0695e7	2026-10-10 18:01:01.108831+00	2026-10-10 19:31:01.108831+00	low	0	0	0	visible	15b2a012-f348-438a-ad0d-098d129a25b0	2026-10-10 18:01:01.114719+00	2026-10-10 18:01:01.114719+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	\N	power_outage	active	\N	\N	b680416d-3b86-4bd2-acef-3abe5f0695e7	2026-10-10 18:01:01.108831+00	2026-10-10 19:31:01.108831+00	low	0	0	0	visible	0a68b5f1-fc29-4198-96e7-fdca1d261a3f	2026-10-10 18:01:01.114719+00	2026-10-10 18:01:01.114719+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	\N	power_outage	active	\N	\N	b680416d-3b86-4bd2-acef-3abe5f0695e7	2026-10-10 18:01:01.108831+00	2026-10-10 19:31:01.108831+00	low	0	0	0	visible	2fdf6354-24cb-4fe1-9a8a-4a2a176efea5	2026-10-10 18:01:01.114719+00	2026-10-10 18:01:01.114719+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	\N	power_outage	active	\N	\N	b680416d-3b86-4bd2-acef-3abe5f0695e7	2026-10-10 18:01:01.108831+00	2026-10-10 19:31:01.108831+00	low	0	0	0	visible	061df5f4-c2e5-421a-a161-220db42f8f9c	2026-10-10 18:01:01.114719+00	2026-10-10 18:01:01.114719+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	\N	power_outage	active	\N	\N	b680416d-3b86-4bd2-acef-3abe5f0695e7	2026-10-10 18:01:01.108831+00	2026-10-10 19:31:01.108831+00	low	0	0	0	visible	f9733465-310c-4fbf-923f-9e46c74908b2	2026-10-10 18:01:01.114719+00	2026-10-10 18:01:01.114719+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	\N	power_outage	active	\N	\N	b680416d-3b86-4bd2-acef-3abe5f0695e7	2026-10-10 18:01:01.108831+00	2026-10-10 19:31:01.108831+00	low	0	0	0	visible	6119a3e8-72e2-43f7-b3a1-931982d63429	2026-10-10 18:01:01.114719+00	2026-10-10 18:01:01.114719+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	\N	power_outage	active	\N	\N	b680416d-3b86-4bd2-acef-3abe5f0695e7	2026-10-10 18:01:01.108831+00	2026-10-10 19:31:01.108831+00	low	0	0	0	visible	b9da392d-ad91-44bd-a9dc-b77d67f0612c	2026-10-10 18:01:01.114719+00	2026-10-10 18:01:01.114719+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	\N	power_outage	active	\N	\N	b680416d-3b86-4bd2-acef-3abe5f0695e7	2026-10-10 18:01:01.108831+00	2026-10-10 19:31:01.108831+00	low	0	0	0	visible	aa118b3b-7cf6-4d07-990a-7fbfb80dc4a0	2026-10-10 18:01:01.114719+00	2026-10-10 18:01:01.114719+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	\N	power_outage	active	\N	\N	b680416d-3b86-4bd2-acef-3abe5f0695e7	2026-10-10 18:01:01.108831+00	2026-10-10 19:31:01.108831+00	low	0	0	0	visible	15b64db9-3779-4fc1-a476-0bd9982ff03b	2026-10-10 18:01:01.114719+00	2026-10-10 18:01:01.114719+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	\N	power_outage	active	\N	\N	b680416d-3b86-4bd2-acef-3abe5f0695e7	2026-10-10 18:01:01.108831+00	2026-10-10 19:31:01.108831+00	low	0	0	0	visible	663298ac-dcdf-4bd7-bfaa-88e5576c6f2f	2026-10-10 18:01:01.114719+00	2026-10-10 18:01:01.114719+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	\N	power_outage	active	\N	\N	b680416d-3b86-4bd2-acef-3abe5f0695e7	2026-10-10 18:01:01.108831+00	2026-10-10 19:31:01.108831+00	low	0	0	0	visible	1a3c6b91-b9c4-44a1-a895-ec8efa70ca05	2026-10-10 18:01:01.114719+00	2026-10-10 18:01:01.114719+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	\N	power_outage	active	\N	\N	b680416d-3b86-4bd2-acef-3abe5f0695e7	2026-10-10 18:01:01.108831+00	2026-10-10 19:31:01.108831+00	low	0	0	0	visible	5532b79a-fbd9-472d-b45b-058888136657	2026-10-10 18:01:01.114719+00	2026-10-10 18:01:01.114719+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	\N	power_outage	active	\N	\N	b680416d-3b86-4bd2-acef-3abe5f0695e7	2026-10-10 18:01:01.108831+00	2026-10-10 19:31:01.108831+00	low	0	0	0	visible	9aca44ef-2c2c-4a4b-a9a4-fefffd8d877d	2026-10-10 18:01:01.114719+00	2026-10-10 18:01:01.114719+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	\N	power_outage	active	\N	\N	b680416d-3b86-4bd2-acef-3abe5f0695e7	2026-10-10 18:01:01.108831+00	2026-10-10 19:31:01.108831+00	low	0	0	0	visible	fb83870d-8b4e-4527-a0d4-89b8bc793eca	2026-10-10 18:01:01.114719+00	2026-10-10 18:01:01.114719+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	\N	power_outage	active	\N	\N	b680416d-3b86-4bd2-acef-3abe5f0695e7	2026-10-10 18:01:01.108831+00	2026-10-10 19:31:01.108831+00	low	0	0	0	visible	bcdd332a-762a-4f2e-ba8c-34c6bc3e5425	2026-10-10 18:01:01.114719+00	2026-10-10 18:01:01.114719+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	\N	power_outage	active	\N	\N	b680416d-3b86-4bd2-acef-3abe5f0695e7	2026-10-10 18:01:01.108831+00	2026-10-10 19:31:01.108831+00	low	0	0	0	visible	8fc6cb75-100f-49ee-b17f-ab4f1efdd191	2026-10-10 18:01:01.114719+00	2026-10-10 18:01:01.114719+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	\N	power_outage	active	\N	\N	b680416d-3b86-4bd2-acef-3abe5f0695e7	2026-10-10 18:01:01.108831+00	2026-10-10 19:31:01.108831+00	low	0	0	0	visible	53508bab-2ac8-4a7a-8a55-555db79c5f23	2026-10-10 18:01:01.114719+00	2026-10-10 18:01:01.114719+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	\N	power_outage	active	\N	\N	b680416d-3b86-4bd2-acef-3abe5f0695e7	2026-10-10 18:01:01.108831+00	2026-10-10 19:31:01.108831+00	low	0	0	0	visible	ec98457a-14b6-4e1d-b7f3-1dd44e2a91a5	2026-10-10 18:01:01.114719+00	2026-10-10 19:20:10.391547+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	41f52af9-4f84-44c4-b63f-0af473116056	emergency	active	testing	\N	5ec88c7c-c351-4e95-b990-79d9afcb0bd2	2026-11-21 14:57:08.747714+00	2026-11-21 15:27:08.712866+00	low	0	0	1	visible	01526d4f-1145-43a7-97be-c7425f4dc68f	2026-11-21 14:57:08.749033+00	2026-11-21 15:01:16.49074+00
\.


--
-- Data for Name: campuses; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.campuses (university_id, slug, name, id, created_at, updated_at, lat, lng) FROM stdin;
a243b143-6a37-4c4b-ae3c-c49b28ebc157	ibadan	Ibadan Campus	e73b4d27-9ac6-4d12-bcdc-4cf2d578ef2c	2026-10-19 15:50:22.741343+00	2026-10-19 15:50:22.741343+00	\N	\N
70cb209f-76c1-463b-b35b-7d764c6ff244	nsukka	Nsukka Campus	26e5548c-0f5f-4404-8c68-3ca53d53d4e2	2026-10-19 15:50:22.802288+00	2026-10-19 15:50:22.802288+00	\N	\N
70cb209f-76c1-463b-b35b-7d764c6ff244	enugu	Enugu Campus (UNEC)	b80a0889-5dba-48f8-8c09-ea9a313ed966	2026-10-19 15:50:22.808173+00	2026-10-19 15:50:22.808173+00	\N	\N
70cb209f-76c1-463b-b35b-7d764c6ff244	ituku-ozalla	Ituku-Ozalla Campus (UNTH)	2650de5e-e6bb-448f-8844-f23885e8850a	2026-10-19 15:50:22.821324+00	2026-10-19 15:50:22.821324+00	\N	\N
70cb209f-76c1-463b-b35b-7d764c6ff244	aba	Aba Campus (UNAC)	84a431a3-2c42-4e33-b0f6-a1cbfc29cb8f	2026-10-19 15:50:22.830613+00	2026-10-19 15:50:22.830613+00	\N	\N
b541581b-465f-4712-ae6e-939d39eed467	ile-ife	Ile-Ife Campus	e4d2cde5-b7e0-451d-a1c4-c824eccdfa63	2026-10-19 15:50:22.84034+00	2026-10-19 15:50:22.84034+00	\N	\N
cc26b75f-e0ac-42a2-8d31-503bb2cb4296	samaru	Samaru Campus	e401a43d-5477-4d1e-a40e-72d2b569d3d1	2026-10-19 15:50:22.860597+00	2026-10-19 15:50:22.860597+00	\N	\N
cc26b75f-e0ac-42a2-8d31-503bb2cb4296	kongo	Kongo Campus	32823e01-0a0a-4c10-898e-0b366fa3ac9b	2026-10-19 15:50:22.868461+00	2026-10-19 15:50:22.868461+00	\N	\N
cc26b75f-e0ac-42a2-8d31-503bb2cb4296	funtua	Funtua Campus	4da1e906-b846-4582-9889-c2c590b77342	2026-10-19 15:50:22.875364+00	2026-10-19 15:50:22.875364+00	\N	\N
7a445b0d-b7e6-40d7-a3ec-d85184466fd9	idi-araba	Idi-Araba Campus	6fb477b8-b3d4-4edb-8c67-6dbde1b2f02e	2026-10-19 15:50:22.898916+00	2026-10-19 15:50:22.898916+00	\N	\N
7a445b0d-b7e6-40d7-a3ec-d85184466fd9	yaba	Yaba Campus	33e77baf-bff7-4f44-833f-2ce91ac1dbe0	2026-10-19 15:50:22.911288+00	2026-10-19 15:50:22.911288+00	\N	\N
bf255fbd-7e87-4e95-94c8-52f680c432bf	ugbowo	Ugbowo Campus	e92ecdeb-9ce7-4813-9fea-cc86cf681259	2026-10-19 15:50:22.938209+00	2026-10-19 15:50:22.938209+00	\N	\N
8e2de1f7-f7e9-444c-8127-45022a4e1afe	calabar	Calabar Campus	a0272f0e-1b49-4fe1-82e7-9784be980079	2026-10-19 15:50:22.953591+00	2026-10-19 15:50:22.953591+00	\N	\N
385c4164-a773-4b4a-ad68-ba10329139d6	old	Old Campus	f6cd05da-f9d5-4780-a813-ac30b460808d	2026-10-19 15:50:22.966522+00	2026-10-19 15:50:22.966522+00	\N	\N
385c4164-a773-4b4a-ad68-ba10329139d6	new	New Campus	7c207ab7-e252-47e2-888f-5833ff6f6af1	2026-10-19 15:50:22.971448+00	2026-10-19 15:50:22.971448+00	\N	\N
8d76f1a6-9d15-48a3-a83a-502293ae85a6	obanla	Obanla Campus	4dc6beb1-cae4-4c69-8718-965e8ce00f1f	2026-10-19 15:50:22.985938+00	2026-10-19 15:50:22.985938+00	\N	\N
25173ad3-6d28-4ecf-b887-e9b6108d526b	main	Main Campus	47f17cfd-6a85-4f74-9ec9-c587dc44c918	2026-10-07 12:16:21.849787+00	2026-10-20 14:01:13.218278+00	8.4826	4.6736
7a445b0d-b7e6-40d7-a3ec-d85184466fd9	akoka	Akoka Campus	6ce2ce01-3c04-4c26-b193-01949e9c295d	2026-10-19 15:50:22.889279+00	2026-10-20 14:01:13.231543+00	6.51821	3.39556
ecf32cb6-4ab8-4cfd-b6eb-06686774a3ce	yaba	Yaba Campus	b69a58a7-828e-4a4b-b0f3-162356444adc	2026-10-24 14:59:28.973702+00	2026-10-24 14:59:28.973702+00	\N	\N
f108a4bd-6d35-424a-b6b9-86d54ada85dc	oko	Oko Campus	67fc45fa-e5d6-4523-9a25-027314fc8e7d	2026-10-24 14:59:28.998535+00	2026-10-24 14:59:28.998535+00	\N	\N
\.


--
-- Data for Name: departments; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.departments (faculty_id, name, code, id, created_at, updated_at) FROM stdin;
200d6927-e726-4c4a-ac65-837b4689134d	Computer Science	CSC	486b48ae-51a8-44fd-b316-e2842d5b4479	2026-10-07 12:16:21.861851+00	2026-10-07 12:16:21.861856+00
dc0ee93a-d6fa-4e03-8367-079b4f7f9bc2	Mechanical Engineering	MEE	576fa415-590e-4b87-a2cb-37d1098fc259	2026-10-07 12:16:21.861866+00	2026-10-07 12:16:21.861867+00
3b77563a-8a25-4f55-981e-8fc9a166067c	Medical/Surgical Nursing	\N	750f0666-79ef-4416-afae-29946f938aa5	2026-10-24 16:09:54.967318+00	2026-10-24 16:09:54.967318+00
3b77563a-8a25-4f55-981e-8fc9a166067c	Maternal & Child Nursing	\N	95ab6184-6674-408a-935a-3ce0d7889178	2026-10-24 16:09:54.987319+00	2026-10-24 16:09:54.987319+00
3b77563a-8a25-4f55-981e-8fc9a166067c	Mental Health Nursing	\N	6299e338-49ea-4127-916d-aa5fea12020c	2026-10-24 16:09:55.00139+00	2026-10-24 16:09:55.00139+00
3b77563a-8a25-4f55-981e-8fc9a166067c	Community Health Nursing	\N	cb3c7c35-9e8d-434b-9e65-603ac3cf7e41	2026-10-24 16:09:55.008801+00	2026-10-24 16:09:55.008801+00
6ad4c0ca-d6ee-4a86-9789-7fa0d1777622	Biological Sciences	\N	fb4ab800-d9da-47c6-ace7-98812104f9d1	2026-10-24 16:09:55.058146+00	2026-10-24 16:09:55.058146+00
6ad4c0ca-d6ee-4a86-9789-7fa0d1777622	Chemical Sciences	\N	2cddbe46-972e-424f-a877-2378bdab60c6	2026-10-24 16:09:55.117215+00	2026-10-24 16:09:55.117215+00
6ad4c0ca-d6ee-4a86-9789-7fa0d1777622	Computer and Information Sciences	\N	e3bb2145-b8ab-4c46-85da-c3dd1f3d7d08	2026-10-24 16:09:55.136896+00	2026-10-24 16:09:55.136896+00
6ad4c0ca-d6ee-4a86-9789-7fa0d1777622	Medical Laboratory Science	\N	0e4c9ba5-cb51-4576-823d-8e8bd968d416	2026-10-24 16:09:55.168272+00	2026-10-24 16:09:55.168272+00
6ad4c0ca-d6ee-4a86-9789-7fa0d1777622	Health Information Management	\N	9a7106eb-a861-40de-8468-59d0e6a52eee	2026-10-24 16:09:55.184305+00	2026-10-24 16:09:55.184305+00
6ad4c0ca-d6ee-4a86-9789-7fa0d1777622	Physics with Electronics	\N	d4c8e406-c008-4f95-975b-4caf276ac48a	2026-10-24 16:09:55.200251+00	2026-10-24 16:09:55.200251+00
55fb7427-a64a-4da5-aaa4-4d4881454676	Accounting	\N	e4ffc70e-c36b-4751-8ae0-744a868f9523	2026-10-24 16:09:55.225279+00	2026-10-24 16:09:55.225279+00
55fb7427-a64a-4da5-aaa4-4d4881454676	Business Administration	\N	d90e156d-95ba-4d8d-aefe-bcbcb3676da0	2026-10-24 16:09:55.250967+00	2026-10-24 16:09:55.250967+00
55fb7427-a64a-4da5-aaa4-4d4881454676	English and Literary Studies	\N	014cf11a-40c2-4f0b-b084-91e3ceb5c2a2	2026-10-24 16:09:55.264122+00	2026-10-24 16:09:55.264122+00
55fb7427-a64a-4da5-aaa4-4d4881454676	Economics	\N	1f110829-9c58-4166-814b-9b2375ac4583	2026-10-24 16:09:55.280459+00	2026-10-24 16:09:55.280459+00
55fb7427-a64a-4da5-aaa4-4d4881454676	Mass Communication	\N	863c6f6d-d13f-45ed-9169-c1ea9c73568a	2026-10-24 16:09:55.294023+00	2026-10-24 16:09:55.294023+00
55fb7427-a64a-4da5-aaa4-4d4881454676	Political Science	\N	397736e5-f81d-49c8-b106-0d3e7a499e13	2026-10-24 16:09:55.308448+00	2026-10-24 16:09:55.308448+00
55fb7427-a64a-4da5-aaa4-4d4881454676	Marketing	\N	962a7460-a1ad-4a82-ade0-b6d4c9b21134	2026-10-24 16:09:55.321201+00	2026-10-24 16:09:55.321201+00
55fb7427-a64a-4da5-aaa4-4d4881454676	Tourism and Hospitality Management	\N	d7de8ccd-116c-4e8e-a584-501aedb28aa4	2026-10-24 16:09:55.337569+00	2026-10-24 16:09:55.337569+00
\.


--
-- Data for Name: faculties; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.faculties (campus_id, name, code, id, created_at, updated_at) FROM stdin;
47f17cfd-6a85-4f74-9ec9-c587dc44c918	Faculty of Communication and Information Sciences	CIS	200d6927-e726-4c4a-ac65-837b4689134d	2026-10-07 12:16:21.856102+00	2026-10-07 12:16:21.856107+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	Faculty of Engineering and Technology	FET	dc0ee93a-d6fa-4e03-8367-079b4f7f9bc2	2026-10-07 12:16:21.856116+00	2026-10-07 12:16:21.856117+00
b69a58a7-828e-4a4b-b0f3-162356444adc	Faculty of Nursing Sciences	\N	3b77563a-8a25-4f55-981e-8fc9a166067c	2026-10-24 16:09:54.917179+00	2026-10-24 16:09:54.917179+00
b69a58a7-828e-4a4b-b0f3-162356444adc	Faculty of Basic Medical and Applied Sciences	\N	6ad4c0ca-d6ee-4a86-9789-7fa0d1777622	2026-10-24 16:09:55.033564+00	2026-10-24 16:09:55.033564+00
b69a58a7-828e-4a4b-b0f3-162356444adc	Faculty of Arts, Management, and Social Sciences	\N	55fb7427-a64a-4da5-aaa4-4d4881454676	2026-10-24 16:09:55.215891+00	2026-10-24 16:09:55.215891+00
\.


--
-- Data for Name: levels; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.levels (programme_id, name, rank, id, created_at, updated_at) FROM stdin;
af49ef1d-2dfd-4a5d-b4a5-7dc642daedb3	100 Level	100	4d0c4b52-e96e-4173-9791-2197153fade7	2026-10-07 12:16:21.872989+00	2026-10-07 12:16:21.872993+00
af49ef1d-2dfd-4a5d-b4a5-7dc642daedb3	200 Level	200	76f618b7-02f1-4a35-bbe2-71b98f2cd2d4	2026-10-07 12:16:21.873002+00	2026-10-07 12:16:21.873003+00
af49ef1d-2dfd-4a5d-b4a5-7dc642daedb3	300 Level	300	64bee4f0-4173-4db5-ba35-67f653778959	2026-10-07 12:16:21.873008+00	2026-10-07 12:16:21.873009+00
af49ef1d-2dfd-4a5d-b4a5-7dc642daedb3	400 Level	400	379ff050-bda7-46f6-ba26-13b1974e4ef4	2026-10-07 12:16:21.873015+00	2026-10-07 12:16:21.873016+00
af49ef1d-2dfd-4a5d-b4a5-7dc642daedb3	500 Level	500	f77affa5-eea3-4875-a31a-a6c1e58c66ce	2026-10-07 12:16:21.873022+00	2026-10-07 12:16:21.873022+00
f218972d-f5b4-450d-892c-3163fcb96c50	100 Level	100	34dbc766-8902-41e3-a7cc-efa9ad03ee1c	2026-10-07 12:16:21.873028+00	2026-10-07 12:16:21.873029+00
f218972d-f5b4-450d-892c-3163fcb96c50	200 Level	200	791422e0-640f-4c62-9abe-577d3b6768f3	2026-10-07 12:16:21.873034+00	2026-10-07 12:16:21.873035+00
f218972d-f5b4-450d-892c-3163fcb96c50	300 Level	300	ddf07acd-d8ae-4b64-9248-45e27931ad7a	2026-10-07 12:16:21.87304+00	2026-10-07 12:16:21.873041+00
f218972d-f5b4-450d-892c-3163fcb96c50	400 Level	400	44db4029-0e49-4d10-b26e-5bbc1276e5be	2026-10-07 12:16:21.873046+00	2026-10-07 12:16:21.873047+00
f218972d-f5b4-450d-892c-3163fcb96c50	500 Level	500	176567a3-b48d-47e7-b927-3a83beec46c1	2026-10-07 12:16:21.873053+00	2026-10-07 12:16:21.873053+00
\.


--
-- Data for Name: location_suggestions; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.location_suggestions (campus_id, proposed_by, name, category, description, lat, lng, status, moderated_by, moderated_at, moderation_note, approved_location_id, id, created_at, updated_at) FROM stdin;
47f17cfd-6a85-4f74-9ec9-c587dc44c918	e6157dcc-4aad-4473-aa9a-11929c07dab8	faculty of art	shop	\N	8.4826	4.6736	rejected	4183fb5f-a399-4f53-ae19-907342a54338	2026-10-10 13:56:57.49955+00	Not real	\N	2c1436ac-1729-4986-a6f5-00e939701585	2026-10-10 13:55:17.267092+00	2026-10-10 13:56:57.500659+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	e6157dcc-4aad-4473-aa9a-11929c07dab8	UNILORIN Biological Garden / Zoo	other	\N	8.481647	4.636917	approved	4183fb5f-a399-4f53-ae19-907342a54338	2026-10-10 14:22:50.09484+00	\N	41f52af9-4f84-44c4-b63f-0af473116056	8816ca7c-c6aa-4c3d-ae91-c6952dc331dd	2026-10-10 14:22:39.060914+00	2026-10-10 14:22:50.101961+00
\.


--
-- Data for Name: locations; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.locations (campus_id, name, category, description, point, polygon, opening_hours, phone, source, status, created_by, verified_by, verified_at, id, created_at, updated_at) FROM stdin;
47f17cfd-6a85-4f74-9ec9-c587dc44c918	UNILORIN Biological Garden / Zoo	other	\N	0101000020E6100000D41055F8338C1240DB6E826F9AF62040	\N	\N	\N	student	approved	e6157dcc-4aad-4473-aa9a-11929c07dab8	4183fb5f-a399-4f53-ae19-907342a54338	2026-10-10 14:22:50.09484+00	41f52af9-4f84-44c4-b63f-0af473116056	2026-10-10 14:22:50.050934+00	2026-10-10 14:22:50.101961+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	Main Library	library	Central library	0101000020E6100000A857CA32C4B112406519E25817F72040	\N	\N	\N	admin	approved	\N	\N	\N	996efdeb-49c9-4d7c-afe8-d0789edf0860	2026-10-10 15:23:14.748457+00	2026-10-10 15:23:14.748457+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	Faculty of Science	building	\N	0101000020E61000008B6CE7FBA9B1124012143FC6DCF52040	\N	\N	\N	admin	approved	\N	\N	\N	4ed74fbd-cb88-4571-8493-66393d5d11de	2026-10-10 15:23:14.748457+00	2026-10-10 15:23:14.748457+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	Faculty of Arts	building	\N	0101000020E61000006C09F9A067B31240F6285C8FC2F52040	\N	\N	\N	admin	approved	\N	\N	\N	bd41e257-13dc-42aa-a31d-317f890af86e	2026-10-10 15:23:14.748457+00	2026-10-10 15:23:14.748457+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	Faculty of Engineering	building	\N	0101000020E610000003098A1F63AE12402FDD240681F52040	\N	\N	\N	admin	approved	\N	\N	\N	77e9257e-5b00-4d26-a7ec-c2c2d242442e	2026-10-10 15:23:14.748457+00	2026-10-10 15:23:14.748457+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	Faculty of CIS	building	Communication and Information Sciences	0101000020E61000001904560E2DB212402C6519E258F72040	\N	\N	\N	admin	approved	\N	\N	\N	4312fe26-285f-4292-be95-ab6f932138c9	2026-10-10 15:23:14.748457+00	2026-10-10 15:23:14.748457+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	Student Union Building	landmark	SUB	0101000020E6100000158C4AEA04B412400F9C33A2B4F72040	\N	\N	\N	admin	approved	\N	\N	\N	e640d827-c81c-4107-bfdd-faf1918e9f15	2026-10-10 15:23:14.748457+00	2026-10-10 15:23:14.748457+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	Main Auditorium	lecture_hall	\N	0101000020E61000006DC5FEB27BB212402B8716D9CEF72040	\N	\N	\N	admin	approved	\N	\N	\N	1bdc52df-70e9-4347-a3c8-4f16e2095dae	2026-10-10 15:23:14.748457+00	2026-10-10 15:23:14.748457+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	University Clinic	clinic	\N	0101000020E61000006891ED7C3FB51240105839B4C8F62040	\N	\N	\N	admin	approved	\N	\N	\N	fd415f65-b2ec-4acf-954c-57be089a6cd8	2026-10-10 15:23:14.748457+00	2026-10-10 15:23:14.748457+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	GTBank ATM	atm	\N	0101000020E6100000C5FEB27BF2B01240D5E76A2BF6F72040	\N	\N	\N	admin	approved	\N	\N	\N	57d0ce82-ba4c-4ff1-86c6-10cd06857dc8	2026-10-10 15:23:14.748457+00	2026-10-10 15:23:14.748457+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	UBA ATM	atm	\N	0101000020E610000030BB270F0BB512402D431CEBE2F62040	\N	\N	\N	admin	approved	\N	\N	\N	0f0a2873-3f5c-46ab-a701-27678ec18804	2026-10-10 15:23:14.748457+00	2026-10-10 15:23:14.748457+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	First Bank ATM	atm	\N	0101000020E6100000FED478E926B11240BC74931804F62040	\N	\N	\N	admin	approved	\N	\N	\N	ab88145b-9155-48b8-9793-3c8c76207475	2026-10-10 15:23:14.748457+00	2026-10-10 15:23:14.748457+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	Old Cafeteria	cafeteria	\N	0101000020E61000001C7C613255B012404850FC1873F72040	\N	\N	\N	admin	approved	\N	\N	\N	c3b7338a-5e60-4f3a-bfa0-c3bbd6b903cf	2026-10-10 15:23:14.748457+00	2026-10-10 15:23:14.748457+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	New Cafeteria	cafeteria	\N	0101000020E61000004E62105839B41240D881734694F62040	\N	\N	\N	admin	approved	\N	\N	\N	21ee71d9-7343-403d-bd5b-956ae35b57e0	2026-10-10 15:23:14.748457+00	2026-10-10 15:23:14.748457+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	Food Court	restaurant	\N	0101000020E6100000A167B3EA73B51240F38E537424F72040	\N	\N	\N	admin	approved	\N	\N	\N	3c17f53f-7319-4765-b589-021a686f8436	2026-10-10 15:23:14.748457+00	2026-10-10 15:23:14.748457+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	Sub Post Office	shop	\N	0101000020E6100000FB5C6DC5FEB21240F2B0506B9AF72040	\N	\N	\N	admin	approved	\N	\N	\N	d7b25742-efb8-48c0-a5ec-0d1e453fdccf	2026-10-10 15:23:14.748457+00	2026-10-10 15:23:14.748457+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	Printing Press	printing	Documents and photocopy	0101000020E6100000A69BC420B0B2124011363CBD52F62040	\N	\N	\N	admin	approved	\N	\N	\N	cda7afb0-b154-4ce9-b5c3-0776c7059254	2026-10-10 15:23:14.748457+00	2026-10-10 15:23:14.748457+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	Main Gate	landmark	Main entrance	0101000020E610000003098A1F63AE1240F0164850FCF82040	\N	\N	\N	admin	approved	\N	\N	\N	f39e84d1-2a10-4e34-968c-b220132a348d	2026-10-10 15:23:14.748457+00	2026-10-10 15:23:14.748457+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	Tanke Gate	landmark	\N	0101000020E6100000560E2DB29DAF124032772D211FF42040	\N	\N	\N	admin	approved	\N	\N	\N	bf559d2a-ecb4-4310-b75c-5d91bf102929	2026-10-10 15:23:14.748457+00	2026-10-10 15:23:14.748457+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	Bus Terminal	transport	Campus shuttle	0101000020E6100000014D840D4FAF124029CB10C7BAF82040	\N	\N	\N	admin	approved	\N	\N	\N	08d65744-72ce-4302-a20f-88e209e6ced4	2026-10-10 15:23:14.748457+00	2026-10-10 15:23:14.748457+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	Sports Complex	sports	\N	0101000020E6100000D881734694B61240F7E461A1D6F42040	\N	\N	\N	admin	approved	\N	\N	\N	de6df38a-1521-487d-9514-a39817787af6	2026-10-10 15:23:14.748457+00	2026-10-10 15:23:14.748457+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	Chapel	worship	\N	0101000020E61000009EEFA7C64BB71240F46C567DAEF62040	\N	\N	\N	admin	approved	\N	\N	\N	86ec46f8-18d1-4857-81dc-4756d8b54a42	2026-10-10 15:23:14.748457+00	2026-10-10 15:23:14.748457+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	Mosque	worship	\N	0101000020E61000008048BF7D1DB812402C6519E258F72040	\N	\N	\N	admin	approved	\N	\N	\N	2c96263a-5d97-463f-aa91-87af8c64edfd	2026-10-10 15:23:14.748457+00	2026-10-10 15:23:14.748457+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	Senior Staff Quarters	hostel	\N	0101000020E610000046B6F3FDD4B8124067D5E76A2BF62040	\N	\N	\N	admin	approved	\N	\N	\N	91cb3220-2108-4797-8d8f-0ba7913fa7bc	2026-10-10 15:23:14.748457+00	2026-10-10 15:23:14.748457+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	Female Hostel Area	hostel	\N	0101000020E6100000D34D621058B91240D93D7958A8F52040	\N	\N	\N	admin	approved	\N	\N	\N	91bb64fb-fa59-45d6-b948-23f99915c433	2026-10-10 15:23:14.748457+00	2026-10-10 15:23:14.748457+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	Male Hostel Area	hostel	\N	0101000020E610000060E5D022DBB912404CA60A4625F52040	\N	\N	\N	admin	approved	\N	\N	\N	0b546f46-45dd-462a-b6a6-66e52c96c909	2026-10-10 15:23:14.748457+00	2026-10-10 15:23:14.748457+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	Postgraduate School	building	\N	0101000020E61000003333333333B31240643BDF4F8DF72040	\N	\N	\N	admin	approved	\N	\N	\N	046fd149-37b8-432e-811f-b2a489138d7e	2026-10-10 15:23:14.748457+00	2026-10-10 15:23:14.748457+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	Faculty of Education	building	\N	0101000020E6100000A69BC420B0B212406891ED7C3FF52040	\N	\N	\N	admin	approved	\N	\N	\N	a922adee-2e43-46c1-b10e-e9f8c5c4eaba	2026-10-10 15:23:14.748457+00	2026-10-10 15:23:14.748457+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	Faculty of Law	building	\N	0101000020E6100000DBF97E6ABCB41240D7A3703D0AF72040	\N	\N	\N	admin	approved	\N	\N	\N	3e2933d4-a8ac-4a5a-8024-5878fa0ccd42	2026-10-10 15:23:14.748457+00	2026-10-10 15:23:14.748457+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	Faculty of Agriculture	building	\N	0101000020E6100000C5FEB27BF2B012404CA60A4625F52040	\N	\N	\N	admin	approved	\N	\N	\N	25e20f68-6996-4846-b9fb-e82e3698a748	2026-10-10 15:23:14.748457+00	2026-10-10 15:23:14.748457+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	Faculty of Social Sciences	building	\N	0101000020E6100000C1CAA145B6B31240105839B4C8F62040	\N	\N	\N	admin	approved	\N	\N	\N	7cfb2329-f4c7-4d04-ab46-7ec94b17a62e	2026-10-10 15:23:14.748457+00	2026-10-10 15:23:14.748457+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	Unilorin Secondary School	building	\N	0101000020E61000008B6CE7FBA9B112404E62105839F42040	\N	\N	\N	admin	approved	\N	\N	\N	0ad30906-2563-4402-ae30-1a71956ae4a2	2026-10-10 15:23:14.748457+00	2026-10-10 15:23:14.748457+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	University Bookshop	shop	\N	0101000020E6100000A69BC420B0B21240D6C56D3480F72040	\N	\N	\N	admin	approved	\N	\N	\N	c59ac197-0628-4f86-9dd6-e49b59076e3b	2026-10-10 15:23:14.748457+00	2026-10-10 15:23:14.748457+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	Zenith Bank ATM	atm	\N	0101000020E6100000713D0AD7A3B012409EEFA7C64BF72040	\N	\N	\N	admin	approved	\N	\N	\N	3bdf6770-5a3e-4135-a061-e75303a55943	2026-10-10 15:23:14.748457+00	2026-10-10 15:23:14.748457+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	Amphitheatre	lecture_hall	\N	0101000020E6100000FED478E926B11240F2D24D6210F82040	\N	\N	\N	admin	approved	\N	\N	\N	25acd9e1-18ef-4374-bab8-d0f5ed6374ca	2026-10-10 15:23:14.748457+00	2026-10-10 15:23:14.748457+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	Computer Science Lab	lab	\N	0101000020E610000051DA1B7C61B21240BADA8AFD65F72040	\N	\N	\N	admin	approved	\N	\N	\N	4b016f3c-2974-4a99-aef7-35a4bcf7233c	2026-10-10 15:23:14.748457+00	2026-10-10 15:23:14.748457+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	Chemistry Lab	lab	\N	0101000020E6100000E02D90A0F8B11240BC74931804F62040	\N	\N	\N	admin	approved	\N	\N	\N	df4b6bb0-7ccd-4c00-b010-eebb5a0ab6dd	2026-10-10 15:23:14.748457+00	2026-10-10 15:23:14.748457+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	Physics Lab	lab	\N	0101000020E61000001904560E2DB21240F6285C8FC2F52040	\N	\N	\N	admin	approved	\N	\N	\N	f28a3b0c-1292-466d-b1a8-32b84a2f6b54	2026-10-10 15:23:14.748457+00	2026-10-10 15:23:14.748457+00
47f17cfd-6a85-4f74-9ec9-c587dc44c918	Biology Lab	lab	\N	0101000020E610000051DA1B7C61B2124012143FC6DCF52040	\N	\N	\N	admin	approved	\N	\N	\N	8225de58-5692-47a8-bb3e-a45911e81863	2026-10-10 15:23:14.748457+00	2026-10-10 15:23:14.748457+00
6ce2ce01-3c04-4c26-b193-01949e9c295d	University of Lagos Library	library	Main library at Akoka campus. Coordinates approximate.	0101000020E6100000315F5E807D340B4048DC63E943171A40	\N	\N	\N	admin	approved	\N	\N	\N	8eaa15cb-d5a0-4336-8706-e6ddb6f8053b	2026-10-20 11:36:06.641417+00	2026-10-20 11:36:06.641417+00
6ce2ce01-3c04-4c26-b193-01949e9c295d	Main Campus (Akoka)	landmark	Akoka campus landmark. Coordinates approximate.	0101000020E610000099D87C5C1B2A0B4034D769A4A5121A40	\N	\N	\N	admin	approved	\N	\N	\N	7f593c3d-454e-4f42-97de-bbb2351bb0a5	2026-10-20 11:36:06.684029+00	2026-10-20 11:36:06.684029+00
\.


--
-- Data for Name: notifications; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.notifications (recipient_id, type, title, body, action_url, campus_id, related_entity_type, related_entity_id, dedupe_key, read_at, dismissed_at, expires_at, id, created_at, updated_at) FROM stdin;
e6157dcc-4aad-4473-aa9a-11929c07dab8	location_suggestion_rejected	Your location suggestion was not approved	Your suggestion "faculty of art" was reviewed but was not approved.	/map/suggest	47f17cfd-6a85-4f74-9ec9-c587dc44c918	location_suggestion	2c1436ac-1729-4986-a6f5-00e939701585	location-suggestion:2c1436ac-1729-4986-a6f5-00e939701585:rejected	\N	\N	\N	6d5346ec-4d00-41f9-9598-e4779fe07856	2026-10-10 13:56:57.509581+00	2026-10-10 13:56:57.509581+00
e6157dcc-4aad-4473-aa9a-11929c07dab8	location_suggestion_approved	Your location suggestion was approved	"UNILORIN Biological Garden / Zoo" has been added to Campus OS. Thanks for helping map your campus.	/map/location/41f52af9-4f84-44c4-b63f-0af473116056	47f17cfd-6a85-4f74-9ec9-c587dc44c918	location_suggestion	8816ca7c-c6aa-4c3d-ae91-c6952dc331dd	location-suggestion:8816ca7c-c6aa-4c3d-ae91-c6952dc331dd:approved	2026-10-10 15:32:26.293117+00	\N	\N	ad648e0d-995a-444c-9498-18f1052bb746	2026-10-10 14:22:50.110342+00	2026-10-10 15:32:26.296204+00
e6157dcc-4aad-4473-aa9a-11929c07dab8	campus_safety_report	New safety report on campus	A new safety report was posted: "Emergency" — testing	/pulse/report/01526d4f-1145-43a7-97be-c7425f4dc68f	47f17cfd-6a85-4f74-9ec9-c587dc44c918	campus_report	01526d4f-1145-43a7-97be-c7425f4dc68f	campus-report:01526d4f-1145-43a7-97be-c7425f4dc68f	\N	\N	\N	7b102545-1dd5-49d9-a9bc-fcc3112a2d20	2026-11-21 14:57:08.938607+00	2026-11-21 14:57:08.938622+00
2fb62d99-cda9-4482-8714-29ccf811eb5f	campus_safety_report	New safety report on campus	A new safety report was posted: "Emergency" — testing	/pulse/report/01526d4f-1145-43a7-97be-c7425f4dc68f	47f17cfd-6a85-4f74-9ec9-c587dc44c918	campus_report	01526d4f-1145-43a7-97be-c7425f4dc68f	campus-report:01526d4f-1145-43a7-97be-c7425f4dc68f	\N	\N	\N	ab5120fd-d8fe-4916-b1b2-344345008e14	2026-11-21 14:57:08.999547+00	2026-11-21 14:57:08.999553+00
b680416d-3b86-4bd2-acef-3abe5f0695e7	campus_safety_report	New safety report on campus	A new safety report was posted: "Emergency" — testing	/pulse/report/01526d4f-1145-43a7-97be-c7425f4dc68f	47f17cfd-6a85-4f74-9ec9-c587dc44c918	campus_report	01526d4f-1145-43a7-97be-c7425f4dc68f	campus-report:01526d4f-1145-43a7-97be-c7425f4dc68f	\N	\N	\N	7a6d44e1-15e9-4d76-ae6a-dbee74dfbd68	2026-11-21 14:57:09.016319+00	2026-11-21 14:57:09.016325+00
e8c377ea-6610-4a3c-89da-0c335392e81d	campus_safety_report	New safety report on campus	A new safety report was posted: "Emergency" — testing	/pulse/report/01526d4f-1145-43a7-97be-c7425f4dc68f	47f17cfd-6a85-4f74-9ec9-c587dc44c918	campus_report	01526d4f-1145-43a7-97be-c7425f4dc68f	campus-report:01526d4f-1145-43a7-97be-c7425f4dc68f	\N	\N	\N	e759f457-42f4-4613-98b4-62638b15c96f	2026-11-21 14:57:09.027618+00	2026-11-21 14:57:09.027626+00
2243ab6b-d49a-4336-a201-cb367907ed2a	campus_safety_report	New safety report on campus	A new safety report was posted: "Emergency" — testing	/pulse/report/01526d4f-1145-43a7-97be-c7425f4dc68f	47f17cfd-6a85-4f74-9ec9-c587dc44c918	campus_report	01526d4f-1145-43a7-97be-c7425f4dc68f	campus-report:01526d4f-1145-43a7-97be-c7425f4dc68f	\N	\N	\N	23438c04-78a7-446c-89a5-558e71b85c09	2026-11-21 14:57:09.040684+00	2026-11-21 14:57:09.040699+00
\.


--
-- Data for Name: programmes; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.programmes (department_id, name, code, id, created_at, updated_at) FROM stdin;
486b48ae-51a8-44fd-b316-e2842d5b4479	B.Sc. Computer Science	CSC	af49ef1d-2dfd-4a5d-b4a5-7dc642daedb3	2026-10-07 12:16:21.867381+00	2026-10-07 12:16:21.867387+00
576fa415-590e-4b87-a2cb-37d1098fc259	B.Eng. Mechanical Engineering	MEE	f218972d-f5b4-450d-892c-3163fcb96c50	2026-10-07 12:16:21.867401+00	2026-10-07 12:16:21.867402+00
fb4ab800-d9da-47c6-ace7-98812104f9d1	B.Sc Biology	\N	9d6fb7e2-e20f-40b6-b00f-23b57f9b8026	2026-10-24 16:09:55.085483+00	2026-10-24 16:09:55.085483+00
fb4ab800-d9da-47c6-ace7-98812104f9d1	B.Sc Microbiology	\N	758ea869-6074-4871-9184-f20541b888f1	2026-10-24 16:09:55.097492+00	2026-10-24 16:09:55.097492+00
fb4ab800-d9da-47c6-ace7-98812104f9d1	B.Sc Biotechnology	\N	aca6dd48-303f-462e-b7d3-e5b6a421096b	2026-10-24 16:09:55.105109+00	2026-10-24 16:09:55.105109+00
2cddbe46-972e-424f-a877-2378bdab60c6	B.Sc Industrial Chemistry	\N	569f429f-529d-472c-b461-d985b5a2096c	2026-10-24 16:09:55.126634+00	2026-10-24 16:09:55.126634+00
e3bb2145-b8ab-4c46-85da-c3dd1f3d7d08	B.Sc Computer Science	\N	7088f777-abb5-4e41-a0d9-92258c6e249a	2026-10-24 16:09:55.148243+00	2026-10-24 16:09:55.148243+00
e3bb2145-b8ab-4c46-85da-c3dd1f3d7d08	B.Sc Information Technology	\N	decd7a59-bc6d-4c58-869b-8328e8fb26d2	2026-10-24 16:09:55.159092+00	2026-10-24 16:09:55.159092+00
0e4c9ba5-cb51-4576-823d-8e8bd968d416	B.MLS Medical Laboratory Science	\N	f011a5ad-5a2c-440c-b61c-ab3cf0f08791	2026-10-24 16:09:55.175963+00	2026-10-24 16:09:55.175963+00
9a7106eb-a861-40de-8468-59d0e6a52eee	B.Sc Health Information Management	\N	9c573fd7-0e6c-4d6f-9e80-f84469ed7313	2026-10-24 16:09:55.191228+00	2026-10-24 16:09:55.191228+00
d4c8e406-c008-4f95-975b-4caf276ac48a	B.Sc Physics with Electronics	\N	f5098775-eacf-4cc4-8e06-aa32727e8d75	2026-10-24 16:09:55.209322+00	2026-10-24 16:09:55.209322+00
e4ffc70e-c36b-4751-8ae0-744a868f9523	B.Sc Accounting	\N	2d38f498-1150-4e7b-b212-9d3d8d034379	2026-10-24 16:09:55.241654+00	2026-10-24 16:09:55.241654+00
d90e156d-95ba-4d8d-aefe-bcbcb3676da0	B.Sc Business Administration	\N	658c17e7-fb9e-43c7-9439-ba54a56ce53a	2026-10-24 16:09:55.258423+00	2026-10-24 16:09:55.258423+00
014cf11a-40c2-4f0b-b084-91e3ceb5c2a2	B.A. English and Literary Studies	\N	b4225060-d7f5-4ee0-904b-80d5c23d5290	2026-10-24 16:09:55.27258+00	2026-10-24 16:09:55.27258+00
1f110829-9c58-4166-814b-9b2375ac4583	B.Sc Economics	\N	9e0494ae-f930-4ad4-bbc8-45bb61a6ed2e	2026-10-24 16:09:55.28678+00	2026-10-24 16:09:55.28678+00
863c6f6d-d13f-45ed-9169-c1ea9c73568a	B.Sc Mass Communication	\N	d9bd0846-5709-4498-b552-40494e34bb50	2026-10-24 16:09:55.298075+00	2026-10-24 16:09:55.298075+00
397736e5-f81d-49c8-b106-0d3e7a499e13	B.Sc Political Science	\N	de6907b9-ce67-44ba-8291-02b91d509de3	2026-10-24 16:09:55.31632+00	2026-10-24 16:09:55.31632+00
962a7460-a1ad-4a82-ade0-b6d4c9b21134	B.Sc Marketing	\N	05ebdb98-ea30-4ede-b25d-4cea459f6339	2026-10-24 16:09:55.330317+00	2026-10-24 16:09:55.330317+00
d7de8ccd-116c-4e8e-a584-501aedb28aa4	B.Sc Tourism and Hospitality Management	\N	684fec66-c6b5-4327-9e79-e93a176a8cfe	2026-10-24 16:09:55.34444+00	2026-10-24 16:09:55.34444+00
\.


--
-- Data for Name: push_subscriptions; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.push_subscriptions (user_id, endpoint, p256dh, auth, user_agent, last_success_at, id, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: report_confirmations; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.report_confirmations (report_id, user_id, kind, id, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: report_flags; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.report_flags (report_id, user_id, reason, id, created_at, updated_at) FROM stdin;
01526d4f-1145-43a7-97be-c7425f4dc68f	5ec88c7c-c351-4e95-b990-79d9afcb0bd2	user_flag	b6755561-5269-4693-b1f8-27075df132f2	2026-11-21 15:01:16.544509+00	2026-11-21 15:01:16.544521+00
\.


--
-- Data for Name: spatial_ref_sys; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.spatial_ref_sys (srid, auth_name, auth_srid, srtext, proj4text) FROM stdin;
\.


--
-- Data for Name: student_profiles; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.student_profiles (user_id, university_id, campus_id, faculty_id, department_id, programme_id, level_id, matric_no, avatar_key, id, created_at, updated_at) FROM stdin;
e6157dcc-4aad-4473-aa9a-11929c07dab8	25173ad3-6d28-4ecf-b887-e9b6108d526b	47f17cfd-6a85-4f74-9ec9-c587dc44c918	200d6927-e726-4c4a-ac65-837b4689134d	486b48ae-51a8-44fd-b316-e2842d5b4479	af49ef1d-2dfd-4a5d-b4a5-7dc642daedb3	4d0c4b52-e96e-4173-9791-2197153fade7	\N	\N	4c61ee0a-73da-4970-99dc-918f74cfbbda	2026-10-07 12:18:37.635075+00	2026-10-07 12:18:48.170381+00
5ec88c7c-c351-4e95-b990-79d9afcb0bd2	25173ad3-6d28-4ecf-b887-e9b6108d526b	47f17cfd-6a85-4f74-9ec9-c587dc44c918	200d6927-e726-4c4a-ac65-837b4689134d	486b48ae-51a8-44fd-b316-e2842d5b4479	af49ef1d-2dfd-4a5d-b4a5-7dc642daedb3	4d0c4b52-e96e-4173-9791-2197153fade7	\N	\N	aaa69be5-63e9-42e9-a811-5ee5a5ad4519	2026-11-21 14:37:45.722919+00	2026-11-21 14:38:07.50022+00
2fb62d99-cda9-4482-8714-29ccf811eb5f	25173ad3-6d28-4ecf-b887-e9b6108d526b	47f17cfd-6a85-4f74-9ec9-c587dc44c918	dc0ee93a-d6fa-4e03-8367-079b4f7f9bc2	576fa415-590e-4b87-a2cb-37d1098fc259	f218972d-f5b4-450d-892c-3163fcb96c50	44db4029-0e49-4d10-b26e-5bbc1276e5be	\N	\N	dcc676fe-6694-4734-be4f-35b9dc25f613	2026-10-21 12:04:30.19334+00	2026-10-21 12:05:10.056521+00
b680416d-3b86-4bd2-acef-3abe5f0695e7	25173ad3-6d28-4ecf-b887-e9b6108d526b	47f17cfd-6a85-4f74-9ec9-c587dc44c918	200d6927-e726-4c4a-ac65-837b4689134d	486b48ae-51a8-44fd-b316-e2842d5b4479	af49ef1d-2dfd-4a5d-b4a5-7dc642daedb3	4d0c4b52-e96e-4173-9791-2197153fade7	\N	\N	5c4a8307-3aff-446c-8ecc-302b82ab319e	2026-10-07 14:54:29.931086+00	2026-10-07 14:54:40.131849+00
e8c377ea-6610-4a3c-89da-0c335392e81d	25173ad3-6d28-4ecf-b887-e9b6108d526b	47f17cfd-6a85-4f74-9ec9-c587dc44c918	200d6927-e726-4c4a-ac65-837b4689134d	486b48ae-51a8-44fd-b316-e2842d5b4479	af49ef1d-2dfd-4a5d-b4a5-7dc642daedb3	\N	\N	\N	f9c62d28-cc34-4dd3-bb55-c121af31fc9b	2026-10-19 15:54:53.810831+00	2026-10-19 15:55:47.70405+00
da0b04e5-86e5-459a-9f36-72ce59b629e2	ecf32cb6-4ab8-4cfd-b6eb-06686774a3ce	b69a58a7-828e-4a4b-b0f3-162356444adc	55fb7427-a64a-4da5-aaa4-4d4881454676	d90e156d-95ba-4d8d-aefe-bcbcb3676da0	658c17e7-fb9e-43c7-9439-ba54a56ce53a	\N	\N	\N	e0ae57d0-064e-45f9-9a04-915e00f77234	2026-10-24 16:49:19.336478+00	2026-10-24 16:49:32.222041+00
7016bb1f-9789-48f1-a860-bd13640996bb	ecf32cb6-4ab8-4cfd-b6eb-06686774a3ce	b69a58a7-828e-4a4b-b0f3-162356444adc	3b77563a-8a25-4f55-981e-8fc9a166067c	cb3c7c35-9e8d-434b-9e65-603ac3cf7e41	658c17e7-fb9e-43c7-9439-ba54a56ce53a	\N	\N	\N	25608c88-f958-4f2d-9972-2be60f8c88f9	2026-10-24 16:44:19.701864+00	2026-10-26 10:47:19.109324+00
2243ab6b-d49a-4336-a201-cb367907ed2a	25173ad3-6d28-4ecf-b887-e9b6108d526b	47f17cfd-6a85-4f74-9ec9-c587dc44c918	200d6927-e726-4c4a-ac65-837b4689134d	486b48ae-51a8-44fd-b316-e2842d5b4479	af49ef1d-2dfd-4a5d-b4a5-7dc642daedb3	4d0c4b52-e96e-4173-9791-2197153fade7	\N	\N	b18c4efc-9ed4-41ed-918c-a43f7843f2b5	2026-10-21 10:47:02.774594+00	2026-10-21 11:00:31.53704+00
fa1fd0e2-9feb-43b7-a3ae-6ddda7d8554f	70cb209f-76c1-463b-b35b-7d764c6ff244	26e5548c-0f5f-4404-8c68-3ca53d53d4e2	\N	\N	\N	\N	\N	\N	f100d0e4-903f-42c0-8ff9-6b3a6c97e8fc	2026-10-21 11:04:54.65409+00	2026-10-21 11:05:16.044339+00
8c851607-350e-4177-8ea5-da9506c0fbc3	ecf32cb6-4ab8-4cfd-b6eb-06686774a3ce	b69a58a7-828e-4a4b-b0f3-162356444adc	55fb7427-a64a-4da5-aaa4-4d4881454676	1f110829-9c58-4166-814b-9b2375ac4583	9e0494ae-f930-4ad4-bbc8-45bb61a6ed2e	\N	\N	\N	a32e70e8-3457-43da-9ea9-35abccf7d846	2026-10-26 11:02:24.863935+00	2026-10-26 11:02:33.911624+00
559e1712-5b45-4c65-9752-5bb945211d83	ecf32cb6-4ab8-4cfd-b6eb-06686774a3ce	b69a58a7-828e-4a4b-b0f3-162356444adc	55fb7427-a64a-4da5-aaa4-4d4881454676	d90e156d-95ba-4d8d-aefe-bcbcb3676da0	658c17e7-fb9e-43c7-9439-ba54a56ce53a	\N	\N	\N	c4b918b1-ad1a-41f7-b31a-2216658cce4f	2026-10-24 15:05:35.738084+00	2026-10-24 16:29:40.566827+00
\.


--
-- Data for Name: tasks; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.tasks (user_id, title, description, due_at, priority, completed_at, id, created_at, updated_at) FROM stdin;
8c851607-350e-4177-8ea5-da9506c0fbc3	Reading	I have to study	2026-11-21	high	2026-11-21 14:30:20.311762+00	1af377ef-42ff-4743-aa74-8991384861f1	2026-11-21 14:30:14.118492+00	2026-11-21 14:30:20.323068+00
\.


--
-- Data for Name: trust_scores; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.trust_scores (user_id, score, tier, accurate_reports, false_reports, confirmations_given, confirmations_received, abuse_flags, id, created_at, updated_at) FROM stdin;
e6157dcc-4aad-4473-aa9a-11929c07dab8	0	new	0	0	0	0	0	50350a31-9c95-44ab-acfd-387fb354900b	2026-10-07 12:25:24.627199+00	2026-10-07 12:25:24.627203+00
b680416d-3b86-4bd2-acef-3abe5f0695e7	0	new	0	0	0	0	0	1472921d-4d3b-4be8-b79f-2d46d4f1982c	2026-10-07 14:54:23.65259+00	2026-10-07 14:54:23.652598+00
46215433-cb2b-4ba9-9e7b-983753164135	0	new	0	0	0	0	0	22d8e82f-f84d-461b-97ea-60a7029a1c31	2026-10-08 13:01:26.134167+00	2026-10-08 13:01:26.134173+00
4183fb5f-a399-4f53-ae19-907342a54338	0	new	0	0	0	0	0	14c26296-cb90-4b61-8426-b8841271c6d5	2026-10-09 15:12:38.629711+00	2026-10-09 15:12:38.629711+00
e8c377ea-6610-4a3c-89da-0c335392e81d	0	new	0	0	0	0	0	1bfb266b-451c-49b3-816e-675199d82ee6	2026-10-19 15:54:44.650522+00	2026-10-19 15:54:44.650527+00
2243ab6b-d49a-4336-a201-cb367907ed2a	0	new	0	0	0	0	0	aeb2f528-f66e-4e0a-a111-7fad6827ba3b	2026-10-21 10:46:26.58435+00	2026-10-21 10:46:26.58436+00
fa1fd0e2-9feb-43b7-a3ae-6ddda7d8554f	0	new	0	0	0	0	0	359b1b36-317c-4a1b-b00a-337dff4675ad	2026-10-21 11:04:43.320103+00	2026-10-21 11:04:43.320107+00
2fb62d99-cda9-4482-8714-29ccf811eb5f	0	new	0	0	0	0	0	5b8b68fd-41b3-40bb-b2f7-f0e4534eb661	2026-10-21 12:04:19.471988+00	2026-10-21 12:04:19.471993+00
559e1712-5b45-4c65-9752-5bb945211d83	0	new	0	0	0	0	0	a560a642-e930-4ef5-9373-4fb879a8e8c0	2026-10-24 14:51:12.259271+00	2026-10-24 14:51:12.259279+00
7016bb1f-9789-48f1-a860-bd13640996bb	0	new	0	0	0	0	0	1b42cd42-ed13-4ef5-abc1-eeff90e43318	2026-10-24 16:33:04.024345+00	2026-10-24 16:33:04.024355+00
da0b04e5-86e5-459a-9f36-72ce59b629e2	0	new	0	0	0	0	0	27766f32-b297-4971-bf76-b16d7a776432	2026-10-24 16:48:18.433416+00	2026-10-24 16:48:18.433424+00
8c851607-350e-4177-8ea5-da9506c0fbc3	0	new	0	0	0	0	0	9988f7dd-f153-42f1-924f-71e1b02f4dd0	2026-10-26 11:02:05.648647+00	2026-10-26 11:02:05.648653+00
5ec88c7c-c351-4e95-b990-79d9afcb0bd2	0	new	0	0	0	0	1	4d274302-d025-497c-8a0f-5d8f499567f0	2026-11-21 14:37:36.635985+00	2026-11-21 15:01:16.633002+00
\.


--
-- Data for Name: universities; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.universities (slug, name, short_name, state, logo_key, is_active, id, created_at, updated_at) FROM stdin;
unilorin	University of Ilorin	UNILORIN	Kwara	\N	t	25173ad3-6d28-4ecf-b887-e9b6108d526b	2026-10-07 12:16:21.843846+00	2026-10-07 12:16:21.843852+00
ui	University of Ibadan	UI	Oyo	\N	t	a243b143-6a37-4c4b-ae3c-c49b28ebc157	2026-10-19 15:50:22.718308+00	2026-10-19 15:50:22.718308+00
unn	University of Nigeria, Nsukka	UNN	Enugu	\N	t	70cb209f-76c1-463b-b35b-7d764c6ff244	2026-10-19 15:50:22.785718+00	2026-10-19 15:50:22.785718+00
oau	Obafemi Awolowo University	OAU	Osun	\N	t	b541581b-465f-4712-ae6e-939d39eed467	2026-10-19 15:50:22.838326+00	2026-10-19 15:50:22.838326+00
abu	Ahmadu Bello University	ABU	Kaduna	\N	t	cc26b75f-e0ac-42a2-8d31-503bb2cb4296	2026-10-19 15:50:22.852211+00	2026-10-19 15:50:22.852211+00
unilag	University of Lagos	UNILAG	Lagos	\N	t	7a445b0d-b7e6-40d7-a3ec-d85184466fd9	2026-10-19 15:50:22.881418+00	2026-10-19 15:50:22.881418+00
uniben	University of Benin	UNIBEN	Edo	\N	t	bf255fbd-7e87-4e95-94c8-52f680c432bf	2026-10-19 15:50:22.92822+00	2026-10-19 15:50:22.92822+00
unical	University of Calabar	UNICAL	Cross River	\N	t	8e2de1f7-f7e9-444c-8127-45022a4e1afe	2026-10-19 15:50:22.943912+00	2026-10-19 15:50:22.943912+00
buk	Bayero University Kano	BUK	Kano	\N	t	385c4164-a773-4b4a-ad68-ba10329139d6	2026-10-19 15:50:22.958588+00	2026-10-19 15:50:22.958588+00
futa	Federal University of Technology, Akure	FUTA	Ondo	\N	t	8d76f1a6-9d15-48a3-a83a-502293ae85a6	2026-10-19 15:50:22.977758+00	2026-10-19 15:50:22.977758+00
trinity	Trinity University, Yaba	Trinity	Lagos	\N	t	ecf32cb6-4ab8-4cfd-b6eb-06686774a3ce	2026-10-24 14:59:28.947984+00	2026-10-24 14:59:28.947984+00
tau	Thomas Adewumi University	TAU	Kwara	\N	t	f108a4bd-6d35-424a-b6b9-86d54ada85dc	2026-10-24 14:59:28.990026+00	2026-10-24 14:59:28.990026+00
\.


--
-- Data for Name: user_sessions; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.user_sessions (user_id, token_hash, ip, user_agent, revoked_at, id, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.users (email, phone, password_hash, display_name, role, status, email_verified_at, last_login_at, id, created_at, updated_at, deleted_at) FROM stdin;
yours@email.com	09087908907	$argon2id$v=19$m=19456,t=2,p=1$yyQ0Gn0hPmp7FZKLi7a0ow$Pa/ma0e8v8E/LmjT2Mz8bPGbvOeNzjrfmASCOcPH7o8	well	student	active	\N	\N	7016bb1f-9789-48f1-a860-bd13640996bb	2026-10-24 16:33:04.006435+00	2026-10-24 16:33:04.006447+00	\N
awwalu253@gmail.com	+2349138577860	$argon2id$v=19$m=19456,t=2,p=1$BSWh73uGRR1Pnpmalc5p8w$uUHDbGTdAycxZqwNMBobJp2PTdzS9CpNDmADvivS9LQ	awwalu	student	active	\N	\N	da0b04e5-86e5-459a-9f36-72ce59b629e2	2026-10-24 16:48:18.423405+00	2026-10-24 16:48:18.423412+00	\N
being@gmail.com	0909489384	$argon2id$v=19$m=19456,t=2,p=1$eRgkfnoxyxLx/sZDTyHRUw$Pm/FeEm5ydQ1EtGOQ2ETfJYCWfosVLnmzzX689E6yFk	well	student	active	\N	2026-10-07 20:07:15.834345+00	b680416d-3b86-4bd2-acef-3abe5f0695e7	2026-10-07 14:54:23.641993+00	2026-10-07 20:07:15.840626+00	\N
asake@gmail.com	09087567423	$argon2id$v=19$m=19456,t=2,p=1$6irVqWA2ht2KIJVjwwbBOA$Ta8uoex+f6AHNLoa++NqGPTfW8K8s0I54MCRzs8hPYA	ololade asake	student	active	\N	\N	8c851607-350e-4177-8ea5-da9506c0fbc3	2026-10-26 11:02:05.637141+00	2026-10-26 11:02:05.637149+00	\N
collei@gmail.com	09094893073	$argon2id$v=19$m=19456,t=2,p=1$idFonfVbOPQQBmEoroMagA$S79MLtBdL2X8WsMD/pMSG2/0MzSgBOwE2x4ZyhVBrlg	event	student	active	\N	\N	5ec88c7c-c351-4e95-b990-79d9afcb0bd2	2026-11-21 14:37:36.616996+00	2026-11-21 14:37:36.617008+00	\N
st3@example.com	\N	$argon2id$v=19$m=19456,t=2,p=1$Tx7i8FXqHXH6SANkLyMiow$l6Iw8gzs6tDtFEbJNRXVO8kzPLvNqQW0SO/X0xndsnc	Stage3	student	active	\N	\N	46215433-cb2b-4ba9-9e7b-983753164135	2026-10-08 13:01:26.127239+00	2026-10-09 16:15:27.585057+00	\N
test5@gmail.com	090875262	$argon2id$v=19$m=19456,t=2,p=1$x6o5FuPMMJZIwlM3v4pHdA$Hv0Qc12hCRyS+GQXbPvr+dQE9zN/tEPeThnJKcw0nts	test User5	student	active	\N	2026-10-10 15:57:02.840675+00	e6157dcc-4aad-4473-aa9a-11929c07dab8	2026-10-07 12:25:24.624298+00	2026-10-10 15:57:02.840675+00	\N
buru@gmail.com	0909489389	$argon2id$v=19$m=19456,t=2,p=1$Zb8OhYVVe8kDwVExGgJT/g$lsN9UT557gvdcriDXMsm0YMCFA2t0m4P1+y8Kf5rx0A	well	student	active	\N	\N	e8c377ea-6610-4a3c-89da-0c335392e81d	2026-10-19 15:54:44.644157+00	2026-10-19 15:54:44.644167+00	\N
emmanuel@gmail.com	0909480983	$argon2id$v=19$m=19456,t=2,p=1$/pjTXHR0gDzD0e9IR4Myow$pO1nxNuk9+m5Jk6fq9e3ccIZhBrPClhlKRj4brpHwq0	event	student	active	\N	\N	2243ab6b-d49a-4336-a201-cb367907ed2a	2026-10-21 10:46:26.557453+00	2026-10-21 10:46:26.557472+00	\N
colli@gmail.com	09049038843	$argon2id$v=19$m=19456,t=2,p=1$WxOkrVHaoE2vCg+9BygOZw$LaxzaV8fq0NIhNA9DiDc9zhB/IqqFL7o/Xl7kbVJCHA	collins ayeni	student	active	\N	\N	fa1fd0e2-9feb-43b7-a3ae-6ddda7d8554f	2026-10-21 11:04:43.31832+00	2026-10-21 11:04:43.318325+00	\N
dik@gmail.com	08098489821	$argon2id$v=19$m=19456,t=2,p=1$TYF8ZLtoATLS72eQyybv5Q$1KmI4lvHi2ZfMSqjOrRluIOydPKcVuAI3/QNKrSgYe8	kok dik	student	active	\N	\N	2fb62d99-cda9-4482-8714-29ccf811eb5f	2026-10-21 12:04:19.46323+00	2026-10-21 12:04:19.463237+00	\N
your@email.com	0907654456	$argon2id$v=19$m=19456,t=2,p=1$Q4/TPQNasJPMwPWRKtalCA$HT7P3nH72EYCVR42kz6gW4gceQYH757KW+42Rr0/wM0	event	student	active	\N	\N	559e1712-5b45-4c65-9752-5bb945211d83	2026-10-24 14:51:12.244316+00	2026-10-24 14:51:12.244326+00	\N
campusos@gmail.com	\N	$argon2id$v=19$m=19456,t=2,p=1$M2W37eDr5qvwgolvPN6QMQ$PgnnPTcj7jQbWR+twV6ChwUDFAAcI9nYIwaOLYRpTSE	Campus-os	platform_admin	active	\N	2026-10-24 15:04:17.658218+00	4183fb5f-a399-4f53-ae19-907342a54338	2026-10-09 15:12:38.618932+00	2026-10-24 15:04:17.716211+00	\N
\.


--
-- Data for Name: geocode_settings; Type: TABLE DATA; Schema: tiger; Owner: -
--

COPY tiger.geocode_settings (name, setting, unit, category, short_desc) FROM stdin;
\.


--
-- Data for Name: pagc_gaz; Type: TABLE DATA; Schema: tiger; Owner: -
--

COPY tiger.pagc_gaz (id, seq, word, stdword, token, is_custom) FROM stdin;
\.


--
-- Data for Name: pagc_lex; Type: TABLE DATA; Schema: tiger; Owner: -
--

COPY tiger.pagc_lex (id, seq, word, stdword, token, is_custom) FROM stdin;
\.


--
-- Data for Name: pagc_rules; Type: TABLE DATA; Schema: tiger; Owner: -
--

COPY tiger.pagc_rules (id, rule, is_custom) FROM stdin;
\.


--
-- Data for Name: topology; Type: TABLE DATA; Schema: topology; Owner: -
--

COPY topology.topology (id, name, srid, "precision", hasz) FROM stdin;
\.


--
-- Data for Name: layer; Type: TABLE DATA; Schema: topology; Owner: -
--

COPY topology.layer (topology_id, layer_id, schema_name, table_name, feature_column, feature_type, level, child_id) FROM stdin;
\.


--
-- Name: topology_id_seq; Type: SEQUENCE SET; Schema: topology; Owner: -
--

SELECT pg_catalog.setval('topology.topology_id_seq', 1, false);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: audit_logs audit_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_pkey PRIMARY KEY (id);


--
-- Name: campus_reports campus_reports_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.campus_reports
    ADD CONSTRAINT campus_reports_pkey PRIMARY KEY (id);


--
-- Name: campuses campuses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.campuses
    ADD CONSTRAINT campuses_pkey PRIMARY KEY (id);


--
-- Name: departments departments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departments
    ADD CONSTRAINT departments_pkey PRIMARY KEY (id);


--
-- Name: faculties faculties_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.faculties
    ADD CONSTRAINT faculties_pkey PRIMARY KEY (id);


--
-- Name: levels levels_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.levels
    ADD CONSTRAINT levels_pkey PRIMARY KEY (id);


--
-- Name: location_suggestions location_suggestions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.location_suggestions
    ADD CONSTRAINT location_suggestions_pkey PRIMARY KEY (id);


--
-- Name: locations locations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.locations
    ADD CONSTRAINT locations_pkey PRIMARY KEY (id);


--
-- Name: notifications notifications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_pkey PRIMARY KEY (id);


--
-- Name: programmes programmes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.programmes
    ADD CONSTRAINT programmes_pkey PRIMARY KEY (id);


--
-- Name: push_subscriptions push_subscriptions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.push_subscriptions
    ADD CONSTRAINT push_subscriptions_pkey PRIMARY KEY (id);


--
-- Name: report_confirmations report_confirmations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.report_confirmations
    ADD CONSTRAINT report_confirmations_pkey PRIMARY KEY (id);


--
-- Name: report_flags report_flags_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.report_flags
    ADD CONSTRAINT report_flags_pkey PRIMARY KEY (id);


--
-- Name: student_profiles student_profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.student_profiles
    ADD CONSTRAINT student_profiles_pkey PRIMARY KEY (id);


--
-- Name: student_profiles student_profiles_user_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.student_profiles
    ADD CONSTRAINT student_profiles_user_id_key UNIQUE (user_id);


--
-- Name: tasks tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_pkey PRIMARY KEY (id);


--
-- Name: trust_scores trust_scores_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trust_scores
    ADD CONSTRAINT trust_scores_pkey PRIMARY KEY (id);


--
-- Name: trust_scores trust_scores_user_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trust_scores
    ADD CONSTRAINT trust_scores_user_id_key UNIQUE (user_id);


--
-- Name: universities universities_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.universities
    ADD CONSTRAINT universities_pkey PRIMARY KEY (id);


--
-- Name: campuses uq_campus_slug_per_uni; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.campuses
    ADD CONSTRAINT uq_campus_slug_per_uni UNIQUE (university_id, slug);


--
-- Name: report_confirmations uq_confirmation_per_user_per_report; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.report_confirmations
    ADD CONSTRAINT uq_confirmation_per_user_per_report UNIQUE (report_id, user_id);


--
-- Name: report_flags uq_flag_per_user_per_report; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.report_flags
    ADD CONSTRAINT uq_flag_per_user_per_report UNIQUE (report_id, user_id);


--
-- Name: levels uq_level_rank_per_programme; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.levels
    ADD CONSTRAINT uq_level_rank_per_programme UNIQUE (programme_id, rank);


--
-- Name: user_sessions user_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_sessions
    ADD CONSTRAINT user_sessions_pkey PRIMARY KEY (id);


--
-- Name: user_sessions user_sessions_token_hash_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_sessions
    ADD CONSTRAINT user_sessions_token_hash_key UNIQUE (token_hash);


--
-- Name: users users_phone_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_phone_key UNIQUE (phone);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: ix_audit_logs_action; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_logs_action ON public.audit_logs USING btree (action);


--
-- Name: ix_audit_logs_actor_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_logs_actor_id ON public.audit_logs USING btree (actor_id);


--
-- Name: ix_campus_reports_campus_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_campus_reports_campus_id ON public.campus_reports USING btree (campus_id);


--
-- Name: ix_campus_reports_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_campus_reports_category ON public.campus_reports USING btree (category);


--
-- Name: ix_campus_reports_expires_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_campus_reports_expires_at ON public.campus_reports USING btree (expires_at);


--
-- Name: ix_campus_reports_location_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_campus_reports_location_id ON public.campus_reports USING btree (location_id);


--
-- Name: ix_campus_reports_reported_by; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_campus_reports_reported_by ON public.campus_reports USING btree (reported_by);


--
-- Name: ix_campus_reports_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_campus_reports_status ON public.campus_reports USING btree (status);


--
-- Name: ix_campuses_university_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_campuses_university_id ON public.campuses USING btree (university_id);


--
-- Name: ix_departments_faculty_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_departments_faculty_id ON public.departments USING btree (faculty_id);


--
-- Name: ix_faculties_campus_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_faculties_campus_id ON public.faculties USING btree (campus_id);


--
-- Name: ix_levels_programme_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_levels_programme_id ON public.levels USING btree (programme_id);


--
-- Name: ix_location_suggestions_campus_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_location_suggestions_campus_id ON public.location_suggestions USING btree (campus_id);


--
-- Name: ix_location_suggestions_proposed_by; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_location_suggestions_proposed_by ON public.location_suggestions USING btree (proposed_by);


--
-- Name: ix_location_suggestions_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_location_suggestions_status ON public.location_suggestions USING btree (status);


--
-- Name: ix_locations_campus_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_locations_campus_id ON public.locations USING btree (campus_id);


--
-- Name: ix_locations_campus_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_locations_campus_status ON public.locations USING btree (campus_id, status);


--
-- Name: ix_locations_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_locations_category ON public.locations USING btree (category);


--
-- Name: ix_locations_point_gist; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_locations_point_gist ON public.locations USING gist (point);


--
-- Name: ix_locations_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_locations_status ON public.locations USING btree (status);


--
-- Name: ix_notifications_campus_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_notifications_campus_created ON public.notifications USING btree (campus_id, created_at);


--
-- Name: ix_notifications_campus_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_notifications_campus_id ON public.notifications USING btree (campus_id);


--
-- Name: ix_notifications_read_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_notifications_read_at ON public.notifications USING btree (read_at);


--
-- Name: ix_notifications_recipient_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_notifications_recipient_created ON public.notifications USING btree (recipient_id, created_at);


--
-- Name: ix_notifications_recipient_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_notifications_recipient_id ON public.notifications USING btree (recipient_id);


--
-- Name: ix_notifications_recipient_unread; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_notifications_recipient_unread ON public.notifications USING btree (recipient_id) WHERE ((read_at IS NULL) AND (dismissed_at IS NULL));


--
-- Name: ix_notifications_related_entity_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_notifications_related_entity_id ON public.notifications USING btree (related_entity_id);


--
-- Name: ix_notifications_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_notifications_type ON public.notifications USING btree (type);


--
-- Name: ix_programmes_department_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_programmes_department_id ON public.programmes USING btree (department_id);


--
-- Name: ix_push_subscriptions_endpoint; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_push_subscriptions_endpoint ON public.push_subscriptions USING btree (endpoint);


--
-- Name: ix_push_subscriptions_user_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_push_subscriptions_user_created ON public.push_subscriptions USING btree (user_id, created_at);


--
-- Name: ix_push_subscriptions_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_push_subscriptions_user_id ON public.push_subscriptions USING btree (user_id);


--
-- Name: ix_report_confirmations_report_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_report_confirmations_report_id ON public.report_confirmations USING btree (report_id);


--
-- Name: ix_report_confirmations_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_report_confirmations_user_id ON public.report_confirmations USING btree (user_id);


--
-- Name: ix_report_flags_report_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_report_flags_report_id ON public.report_flags USING btree (report_id);


--
-- Name: ix_report_flags_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_report_flags_user_id ON public.report_flags USING btree (user_id);


--
-- Name: ix_reports_campus_status_expires; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_reports_campus_status_expires ON public.campus_reports USING btree (campus_id, status, expires_at);


--
-- Name: ix_tasks_completed_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tasks_completed_at ON public.tasks USING btree (completed_at);


--
-- Name: ix_tasks_due_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tasks_due_at ON public.tasks USING btree (due_at);


--
-- Name: ix_tasks_user_completed_due; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tasks_user_completed_due ON public.tasks USING btree (user_id, completed_at, due_at);


--
-- Name: ix_tasks_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tasks_user_id ON public.tasks USING btree (user_id);


--
-- Name: ix_universities_slug; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_universities_slug ON public.universities USING btree (slug);


--
-- Name: ix_user_sessions_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_sessions_user_id ON public.user_sessions USING btree (user_id);


--
-- Name: ix_users_email; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_users_email ON public.users USING btree (email);


--
-- Name: uq_notifications_recipient_dedupe; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_notifications_recipient_dedupe ON public.notifications USING btree (recipient_id, dedupe_key) WHERE (dedupe_key IS NOT NULL);


--
-- Name: audit_logs audit_logs_actor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: campus_reports campus_reports_campus_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.campus_reports
    ADD CONSTRAINT campus_reports_campus_id_fkey FOREIGN KEY (campus_id) REFERENCES public.campuses(id) ON DELETE CASCADE;


--
-- Name: campus_reports campus_reports_location_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.campus_reports
    ADD CONSTRAINT campus_reports_location_id_fkey FOREIGN KEY (location_id) REFERENCES public.locations(id) ON DELETE SET NULL;


--
-- Name: campus_reports campus_reports_reported_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.campus_reports
    ADD CONSTRAINT campus_reports_reported_by_fkey FOREIGN KEY (reported_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: campuses campuses_university_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.campuses
    ADD CONSTRAINT campuses_university_id_fkey FOREIGN KEY (university_id) REFERENCES public.universities(id) ON DELETE CASCADE;


--
-- Name: departments departments_faculty_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departments
    ADD CONSTRAINT departments_faculty_id_fkey FOREIGN KEY (faculty_id) REFERENCES public.faculties(id) ON DELETE CASCADE;


--
-- Name: faculties faculties_campus_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.faculties
    ADD CONSTRAINT faculties_campus_id_fkey FOREIGN KEY (campus_id) REFERENCES public.campuses(id) ON DELETE CASCADE;


--
-- Name: levels levels_programme_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.levels
    ADD CONSTRAINT levels_programme_id_fkey FOREIGN KEY (programme_id) REFERENCES public.programmes(id) ON DELETE CASCADE;


--
-- Name: location_suggestions location_suggestions_approved_location_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.location_suggestions
    ADD CONSTRAINT location_suggestions_approved_location_id_fkey FOREIGN KEY (approved_location_id) REFERENCES public.locations(id) ON DELETE SET NULL;


--
-- Name: location_suggestions location_suggestions_campus_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.location_suggestions
    ADD CONSTRAINT location_suggestions_campus_id_fkey FOREIGN KEY (campus_id) REFERENCES public.campuses(id) ON DELETE CASCADE;


--
-- Name: location_suggestions location_suggestions_moderated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.location_suggestions
    ADD CONSTRAINT location_suggestions_moderated_by_fkey FOREIGN KEY (moderated_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: location_suggestions location_suggestions_proposed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.location_suggestions
    ADD CONSTRAINT location_suggestions_proposed_by_fkey FOREIGN KEY (proposed_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: locations locations_campus_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.locations
    ADD CONSTRAINT locations_campus_id_fkey FOREIGN KEY (campus_id) REFERENCES public.campuses(id) ON DELETE CASCADE;


--
-- Name: locations locations_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.locations
    ADD CONSTRAINT locations_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: locations locations_verified_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.locations
    ADD CONSTRAINT locations_verified_by_fkey FOREIGN KEY (verified_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: notifications notifications_campus_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_campus_id_fkey FOREIGN KEY (campus_id) REFERENCES public.campuses(id) ON DELETE SET NULL;


--
-- Name: notifications notifications_recipient_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_recipient_id_fkey FOREIGN KEY (recipient_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: programmes programmes_department_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.programmes
    ADD CONSTRAINT programmes_department_id_fkey FOREIGN KEY (department_id) REFERENCES public.departments(id) ON DELETE CASCADE;


--
-- Name: push_subscriptions push_subscriptions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.push_subscriptions
    ADD CONSTRAINT push_subscriptions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: report_confirmations report_confirmations_report_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.report_confirmations
    ADD CONSTRAINT report_confirmations_report_id_fkey FOREIGN KEY (report_id) REFERENCES public.campus_reports(id) ON DELETE CASCADE;


--
-- Name: report_confirmations report_confirmations_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.report_confirmations
    ADD CONSTRAINT report_confirmations_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: report_flags report_flags_report_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.report_flags
    ADD CONSTRAINT report_flags_report_id_fkey FOREIGN KEY (report_id) REFERENCES public.campus_reports(id) ON DELETE CASCADE;


--
-- Name: report_flags report_flags_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.report_flags
    ADD CONSTRAINT report_flags_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: student_profiles student_profiles_campus_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.student_profiles
    ADD CONSTRAINT student_profiles_campus_id_fkey FOREIGN KEY (campus_id) REFERENCES public.campuses(id);


--
-- Name: student_profiles student_profiles_department_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.student_profiles
    ADD CONSTRAINT student_profiles_department_id_fkey FOREIGN KEY (department_id) REFERENCES public.departments(id);


--
-- Name: student_profiles student_profiles_faculty_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.student_profiles
    ADD CONSTRAINT student_profiles_faculty_id_fkey FOREIGN KEY (faculty_id) REFERENCES public.faculties(id);


--
-- Name: student_profiles student_profiles_level_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.student_profiles
    ADD CONSTRAINT student_profiles_level_id_fkey FOREIGN KEY (level_id) REFERENCES public.levels(id);


--
-- Name: student_profiles student_profiles_programme_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.student_profiles
    ADD CONSTRAINT student_profiles_programme_id_fkey FOREIGN KEY (programme_id) REFERENCES public.programmes(id);


--
-- Name: student_profiles student_profiles_university_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.student_profiles
    ADD CONSTRAINT student_profiles_university_id_fkey FOREIGN KEY (university_id) REFERENCES public.universities(id);


--
-- Name: student_profiles student_profiles_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.student_profiles
    ADD CONSTRAINT student_profiles_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: tasks tasks_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: trust_scores trust_scores_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trust_scores
    ADD CONSTRAINT trust_scores_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: user_sessions user_sessions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_sessions
    ADD CONSTRAINT user_sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

