--
-- PostgreSQL database dump
--

\restrict c3sEQ2uuEpk6aDV2eYzfMIJUzLadKoo3AB6oNiYgViscelhPDSaWxjT9TFNVAjY

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

--
-- Name: create_image(text, text, bigint, text); Type: FUNCTION; Schema: public; Owner: root_user
--

CREATE FUNCTION public.create_image(p_filename text, p_original_name text, p_size bigint, p_file_type text) RETURNS bigint
    LANGUAGE plpgsql
    AS $$
DECLARE
    v_id BIGINT;
BEGIN
    IF p_filename IS NULL OR btrim(p_filename) = '' THEN
        RAISE EXCEPTION 'filename must not be empty'
            USING ERRCODE = '22023';
    END IF;

    IF p_original_name IS NULL OR btrim(p_original_name) = '' THEN
        RAISE EXCEPTION 'original_name must not be empty'
            USING ERRCODE = '22023';
    END IF;

    IF p_size IS NULL OR p_size < 0 THEN
        RAISE EXCEPTION 'size must be non-negative'
            USING ERRCODE = '22023';
    END IF;

    IF p_file_type IS NULL OR btrim(p_file_type) = '' THEN
        RAISE EXCEPTION 'file_type must not be empty'
            USING ERRCODE = '22023';
    END IF;

    INSERT INTO public.images (
        filename,
        original_name,
        size,
        file_type
    )
    VALUES (
        p_filename,
        p_original_name,
        p_size,
        p_file_type
    )
    RETURNING id INTO v_id;

    RETURN v_id;
END;
$$;


ALTER FUNCTION public.create_image(p_filename text, p_original_name text, p_size bigint, p_file_type text) OWNER TO root_user;

--
-- Name: delete_image(bigint); Type: FUNCTION; Schema: public; Owner: root_user
--

CREATE FUNCTION public.delete_image(p_image_id bigint) RETURNS text
    LANGUAGE plpgsql
    AS $$
DECLARE
    v_original_name TEXT;
BEGIN
    IF p_image_id IS NULL OR p_image_id <= 0 THEN
        RAISE EXCEPTION 'image_id must be positive'
            USING ERRCODE = '22023';
    END IF;

    DELETE FROM public.images
    WHERE id = p_image_id RETURNING original_name
    INTO v_original_name;
    RETURN v_original_name;
END;
$$;


ALTER FUNCTION public.delete_image(p_image_id bigint) OWNER TO root_user;

--
-- Name: get_image_filename(bigint); Type: FUNCTION; Schema: public; Owner: root_user
--

CREATE FUNCTION public.get_image_filename(p_image_id bigint) RETURNS text
    LANGUAGE sql STABLE
    AS $$
    SELECT filename
    FROM public.images
    WHERE id = p_image_id
      AND p_image_id > 0;
$$;


ALTER FUNCTION public.get_image_filename(p_image_id bigint) OWNER TO root_user;

--
-- Name: get_images(integer, integer); Type: FUNCTION; Schema: public; Owner: root_user
--

CREATE FUNCTION public.get_images(p_page integer DEFAULT 1, p_page_size integer DEFAULT 10) RETURNS jsonb
    LANGUAGE plpgsql STABLE
    AS $$
DECLARE
    v_page      INTEGER;
    v_page_size INTEGER;
    v_offset    BIGINT;
    v_result    JSONB;
BEGIN
    v_page := COALESCE(p_page, 1);
    v_page_size := COALESCE(p_page_size, 10);
    v_offset := (v_page::BIGINT - 1) * v_page_size;
    SELECT COALESCE(
        jsonb_agg(
            to_jsonb(page_rows)
            ORDER BY page_rows.upload_time DESC, page_rows.id DESC
        ),
        '[]'::JSONB
    )
    INTO v_result
    FROM (
        SELECT
            id,
            filename,
            original_name,
            size,
            file_type,
            upload_time
        FROM public.images
        ORDER BY upload_time DESC, id DESC
        LIMIT v_page_size
        OFFSET v_offset
    ) AS page_rows;

    RETURN v_result;
END;
$$;


ALTER FUNCTION public.get_images(p_page integer, p_page_size integer) OWNER TO root_user;

--
-- Name: get_pagination(integer, integer); Type: FUNCTION; Schema: public; Owner: root_user
--

CREATE FUNCTION public.get_pagination(p_page integer DEFAULT 1, p_page_size integer DEFAULT 10) RETURNS jsonb
    LANGUAGE plpgsql STABLE
    AS $$
DECLARE
    v_page        INTEGER;
    v_page_size   INTEGER;
    v_total_items BIGINT;
    v_total_pages BIGINT;
BEGIN
    v_page := GREATEST(COALESCE(p_page, 1), 1);

    v_page_size := LEAST(
        GREATEST(COALESCE(p_page_size, 10), 1),
        100
    );

    SELECT COUNT(*)
    INTO v_total_items
    FROM public.images;

    v_total_pages :=
        CEIL(v_total_items::NUMERIC / v_page_size)::BIGINT;

    RETURN jsonb_build_object(
        'total_items', v_total_items,
        'page', v_page,
        'page_size', v_page_size,
        'total_pages', v_total_pages,
        'has_previous', v_page > 1,
        'has_next', v_page < v_total_pages
    );
END;
$$;


ALTER FUNCTION public.get_pagination(p_page integer, p_page_size integer) OWNER TO root_user;

--
-- Name: update_image(bigint, text, bigint, text); Type: FUNCTION; Schema: public; Owner: root_user
--

CREATE FUNCTION public.update_image(p_image_id bigint, p_original_name text, p_size bigint, p_file_type text) RETURNS boolean
    LANGUAGE plpgsql
    AS $$
DECLARE
    v_updated INTEGER;
BEGIN
    IF p_image_id IS NULL OR p_image_id <= 0 THEN
        RAISE EXCEPTION 'image_id must be positive'
            USING ERRCODE = '22023';
    END IF;

    IF p_original_name IS NULL OR btrim(p_original_name) = '' THEN
        RAISE EXCEPTION 'original_name must not be empty'
            USING ERRCODE = '22023';
    END IF;

    IF p_size IS NULL OR p_size < 0 THEN
        RAISE EXCEPTION 'size must be non-negative'
            USING ERRCODE = '22023';
    END IF;

    IF p_file_type IS NULL OR btrim(p_file_type) = '' THEN
        RAISE EXCEPTION 'file_type must not be empty'
            USING ERRCODE = '22023';
    END IF;

    UPDATE public.images
    SET
        original_name = p_original_name,
        size = p_size,
        file_type = p_file_type
    WHERE id = p_image_id;

    GET DIAGNOSTICS v_updated = ROW_COUNT;

    RETURN v_updated > 0;
END;
$$;


ALTER FUNCTION public.update_image(p_image_id bigint, p_original_name text, p_size bigint, p_file_type text) OWNER TO root_user;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: images; Type: TABLE; Schema: public; Owner: root_user
--

CREATE TABLE public.images (
    id bigint NOT NULL,
    filename text NOT NULL,
    original_name text NOT NULL,
    size bigint NOT NULL,
    upload_time timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    file_type text NOT NULL,
    CONSTRAINT images_size_check CHECK ((size >= 0))
);


ALTER TABLE public.images OWNER TO root_user;

--
-- Name: images_id_seq; Type: SEQUENCE; Schema: public; Owner: root_user
--

ALTER TABLE public.images ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.images_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Data for Name: images; Type: TABLE DATA; Schema: public; Owner: root_user
--

COPY public.images (id, filename, original_name, size, upload_time, file_type) FROM stdin;
18	fd0505e1868a4bc98514b343a5a6e0e6.jpg	photo_2026-08-25_15-26-14.jpg	116021	2026-10-11 13:22:15.479433+00	jpg
19	6116b7962ebe495f9d405b54fcfeed58.jpg	photo_2026-08-25_14-32-18.jpg	120004	2026-10-11 13:22:15.479433+00	jpg
21	3a31b4e49b1448f2a2efd45535a6d1a1.jpg	photo_2026-08-25_14-32-15.jpg	131453	2026-10-11 13:22:15.479433+00	jpg
29	d5e42bd1cb604bad998303adc0a15b53.jpg	131898-mountainous_landforms-mountain-dock-alps-rock-1920x1080.jpg	343842	2026-10-11 13:23:17.198618+00	jpg
\.


--
-- Name: images_id_seq; Type: SEQUENCE SET; Schema: public; Owner: root_user
--

SELECT pg_catalog.setval('public.images_id_seq', 30, true);


--
-- Name: images images_pkey; Type: CONSTRAINT; Schema: public; Owner: root_user
--

ALTER TABLE ONLY public.images
    ADD CONSTRAINT images_pkey PRIMARY KEY (id);


--
-- Name: idx_images_upload_time_id; Type: INDEX; Schema: public; Owner: root_user
--

CREATE INDEX idx_images_upload_time_id ON public.images USING btree (upload_time DESC, id DESC);


--
-- Name: TABLE images; Type: ACL; Schema: public; Owner: root_user
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.images TO PUBLIC;


--
-- Name: SEQUENCE images_id_seq; Type: ACL; Schema: public; Owner: root_user
--

GRANT SELECT,USAGE ON SEQUENCE public.images_id_seq TO PUBLIC;


--
-- PostgreSQL database dump complete
--

\unrestrict c3sEQ2uuEpk6aDV2eYzfMIJUzLadKoo3AB6oNiYgViscelhPDSaWxjT9TFNVAjY

