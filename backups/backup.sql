--
-- PostgreSQL database dump
--

\restrict JxmwPnlyNIuyhI4wYpGCHId9WxYbWE4yaaTDpLf9Rnu777LUZ59sIC3v4Dsj03Q

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
1	31ad06f071314cf2bfb5d1eeaf774d14.png	Снимок экрана_20260916_210038.png	34148	2026-10-11 13:37:24.456261	png
5	acdd3dbded474ed8b17918789a4082d5.jpg	wp11849570-219-4k-wallpapers.jpg	862178	2026-10-11 13:40:06.281366	jpg
6	f97a42f5af904eb6ba91a1108dd33692.png	Снимок экрана_20260916_210038.png	34148	2026-10-11 13:40:06.281366	png
18	8288b74f91314da0a2cedf8872d808b3.jpg	photo_2026-08-25_14-32-02.jpg	337010	2026-10-11 13:41:53.291319	jpg
19	38e6c6576b764ed38cde99ee34f49a04.jpg	photo_2026-08-25_14-32-10.jpg	336164	2026-10-11 13:41:53.291319	jpg
20	555bdd2b13d84297830275a21c75d45f.jpg	photo_2026-08-25_14-32-12.jpg	344280	2026-10-11 13:41:53.291319	jpg
21	f23940e00e3a4a93b7197eeb892f9562.jpg	photo_2026-08-25_14-32-15.jpg	131453	2026-10-11 13:41:53.291319	jpg
22	4426269c517347a0a5cbce2c7e7c4f1c.jpg	photo_2026-08-25_14-32-18.jpg	120004	2026-10-11 13:41:53.291319	jpg
23	38d5933dbf794c32b65b824b2f788fcb.jpg	photo_2026-08-25_15-26-14.jpg	116021	2026-10-11 13:41:53.291319	jpg
24	a74801194c4f4221b5a091d2334e5758.jpg	photo_2026-08-25_15-26-17.jpg	98708	2026-10-11 13:41:53.291319	jpg
25	fbfedc80ba5946cca53d30465159c93f.jpg	ВБ-2.jpg	202869	2026-10-11 13:41:53.291319	jpg
26	326e7f55ae0c43f385ed9d7e2d5450c4.jpg	ВБ-3.jpg	200880	2026-10-11 13:41:53.291319	jpg
27	529d802412c649ec9792d29737a444f1.jpg	ВБ-4.jpg	232631	2026-10-11 13:41:53.291319	jpg
28	ae00c6bc077d4081876c7f092f328402.jpg	ВБ-5.jpg	245879	2026-10-11 13:41:53.291319	jpg
29	f9c4908bfbc1435794155a82bd3eb8db.jpg	ВБ-6.jpg	218170	2026-10-11 13:41:53.291319	jpg
\.


--
-- Name: images_id_seq; Type: SEQUENCE SET; Schema: public; Owner: root_user
--

SELECT pg_catalog.setval('public.images_id_seq', 29, true);


--
-- Name: images images_pkey; Type: CONSTRAINT; Schema: public; Owner: root_user
--

ALTER TABLE ONLY public.images
    ADD CONSTRAINT images_pkey PRIMARY KEY (id);


--
-- PostgreSQL database dump complete
--

\unrestrict JxmwPnlyNIuyhI4wYpGCHId9WxYbWE4yaaTDpLf9Rnu777LUZ59sIC3v4Dsj03Q

