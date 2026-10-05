--
-- PostgreSQL database dump
--

\restrict eR4fbokxpy3rdhcr81vOmeagkXEBQbX9XH2QP1FcB4uJGFBobN9h87eoIIPnqdU

-- Dumped from database version 18.6
-- Dumped by pg_dump version 18.6

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: images; Type: TABLE; Schema: public; Owner: root_user
--

CREATE TABLE public.images (
    id integer NOT NULL,
    filename text NOT NULL,
    original_name text NOT NULL,
    size integer NOT NULL,
    upload_time timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    file_type text NOT NULL
);


ALTER TABLE public.images OWNER TO root_user;

--
-- Name: images_id_seq; Type: SEQUENCE; Schema: public; Owner: root_user
--

CREATE SEQUENCE public.images_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.images_id_seq OWNER TO root_user;

--
-- Name: images_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: root_user
--

ALTER SEQUENCE public.images_id_seq OWNED BY public.images.id;


--
-- Name: images id; Type: DEFAULT; Schema: public; Owner: root_user
--

ALTER TABLE ONLY public.images ALTER COLUMN id SET DEFAULT nextval('public.images_id_seq'::regclass);


--
-- Data for Name: images; Type: TABLE DATA; Schema: public; Owner: root_user
--

COPY public.images (id, filename, original_name, size, upload_time, file_type) FROM stdin;
4	904e913bab9d442c8d478f293cd36fb7.jpg	photo_2026-08-25_14-32-15.jpg	131453	2026-10-05 06:17:12.002766	jpg
5	850a442e0cb3400d95567e0f6d55f3e3.jpg	photo_2026-08-25_14-32-18.jpg	120004	2026-10-05 06:17:12.039764	jpg
8	cb783f87148346688c3573ab9c875778.jpg	ВБ-2.jpg	202869	2026-10-05 06:17:12.178447	jpg
10	a4047c686e424fd7aca356d8c3f6382a.jpg	ВБ-4.jpg	232631	2026-10-05 06:17:12.281349	jpg
11	ed416332626a475989e160a5e2be65dc.jpg	ВБ-5.jpg	245879	2026-10-05 06:17:12.344183	jpg
12	2e6435672d114aea8c143c07580ce8a0.jpg	ВБ-6.jpg	218170	2026-10-05 06:17:12.391258	jpg
\.


--
-- Name: images_id_seq; Type: SEQUENCE SET; Schema: public; Owner: root_user
--

SELECT pg_catalog.setval('public.images_id_seq', 12, true);


--
-- Name: images images_pkey; Type: CONSTRAINT; Schema: public; Owner: root_user
--

ALTER TABLE ONLY public.images
    ADD CONSTRAINT images_pkey PRIMARY KEY (id);


--
-- PostgreSQL database dump complete
--

\unrestrict eR4fbokxpy3rdhcr81vOmeagkXEBQbX9XH2QP1FcB4uJGFBobN9h87eoIIPnqdU

