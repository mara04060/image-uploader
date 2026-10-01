document.addEventListener('DOMContentLoaded', () => {

    const API_BASE_URL = 'http://localhost:8080';


    /*
     * Current page.
     *
     * Backend is the source of truth for pagination.
     */

    let page = 1;


    const fileListWrapper =
        document.getElementById('file-list-wrapper');


    const uploadRedirectButton =
        document.getElementById('upload-tab-btn');


    /* =========================================================
     * F5 and Escape keys
     * ========================================================= */

    document.addEventListener('keydown', (event) => {

        if (event.key === 'F5' || event.key === 'Escape') {

            event.preventDefault();

            window.location.href = 'upload.html';
        }
    });


    /* =========================================================
     * Update active tab
     * ========================================================= */

    const updateTabStyles = () => {

        const uploadTab =
            document.getElementById('upload-tab-btn');


        const imagesTab =
            document.getElementById('images-tab-btn');


        const isImagesPage =
            window.location.pathname.includes('images.html');


        if (uploadTab) {
            uploadTab.classList.remove(
                'upload__tab--active'
            );
        }


        if (imagesTab) {
            imagesTab.classList.remove(
                'upload__tab--active'
            );
        }


        if (isImagesPage) {

            if (imagesTab) {

                imagesTab.classList.add(
                    'upload__tab--active'
                );
            }

        } else {

            if (uploadTab) {

                uploadTab.classList.add(
                    'upload__tab--active'
                );
            }
        }
    };


    /* =========================================================
     * GET images list
     *
     * GET /images-list?page=1
     *
     * Backend response:
     *
     * {
     *     "items": [],
     *
     *     "pagination": {
     *         "total_items": 22,
     *         "page": 1,
     *         "total_pages": 3,
     *         "has_previous": false,
     *         "has_next": true
     *     }
     * }
     * ========================================================= */

    const getImages = async () => {

        try {

            console.log(
                `[API] GET /images-list?page=${page}`
            );


            const response = await fetch(
                `${API_BASE_URL}/images-list?page=${page}`,
                {
                    method: 'GET'
                }
            );


            console.log(
                '[API] /images-list response:',
                response.status
            );


            if (!response.ok) {

                throw new Error(
                    `Сервер повернув HTTP ${response.status}`
                );
            }


            /*
             * Read response as text first.
             */

            const responseText =
                await response.text();


            console.log(
                '[API] /images-list body:',
                responseText
            );


            /*
             * Empty response is an error.
             */

            if (!responseText.trim()) {

                throw new Error(
                    'Сервер повернув порожню відповідь.'
                );
            }


            let data;


            /*
             * Parse JSON.
             */

            try {

                data =
                    JSON.parse(responseText);

            } catch (error) {

                throw new Error(
                    'Сервер повернув некоректний JSON.'
                );
            }


            /* =================================================
             * Validate root object
             * ================================================= */

            if (
                !data ||
                typeof data !== 'object' ||
                Array.isArray(data)
            ) {

                throw new Error(
                    'Некоректний формат відповіді. ' +
                    'Очікувався JSON-об\'єкт.'
                );
            }


            /* =================================================
             * Validate items
             * ================================================= */

            if (!Array.isArray(data.items)) {

                throw new Error(
                    'Некоректний формат відповіді. ' +
                    'Поле "items" повинно бути масивом.'
                );
            }


            /* =================================================
             * Validate pagination
             * ================================================= */

            if (
                !data.pagination ||
                typeof data.pagination !== 'object' ||
                Array.isArray(data.pagination)
            ) {

                throw new Error(
                    'Некоректний формат відповіді. ' +
                    'Відсутнє поле "pagination".'
                );
            }


            const pagination =
                data.pagination;


            /* =================================================
             * Validate pagination.page
             * ================================================= */

            if (
                pagination.page === undefined ||
                pagination.page === null
            ) {

                throw new Error(
                    'У pagination відсутнє поле "page".'
                );
            }


            /* =================================================
             * Validate pagination.total_pages
             * ================================================= */

            if (
                pagination.total_pages === undefined ||
                pagination.total_pages === null
            ) {

                throw new Error(
                    'У pagination відсутнє поле "total_pages".'
                );
            }


            /* =================================================
             * Validate has_previous
             * ================================================= */

            if (
                typeof pagination.has_previous !== 'boolean'
            ) {

                throw new Error(
                    'Поле "has_previous" повинно бути boolean.'
                );
            }


            /* =================================================
             * Validate has_next
             * ================================================= */

            if (
                typeof pagination.has_next !== 'boolean'
            ) {

                throw new Error(
                    'Поле "has_next" повинно бути boolean.'
                );
            }


            /*
             * Backend is the source of truth.
             *
             * Synchronize current page.
             */

            page =
                Number(pagination.page);


            return data;

        } catch (error) {

            console.error(
                '[API] Помилка отримання списку:',
                error
            );


            alert(
                'Помилка під час отримання списку зображень:\n\n' +
                error.message
            );


            return null;
        }
    };


    /* =========================================================
     * Render pagination
     * ========================================================= */

    const renderPagination = (paginationData) => {

        /*
         * IMPORTANT:
         *
         * Use the existing <section id="pagination">
         * from HTML.
         *
         * Do NOT remove it.
         * Do NOT create another element with id="pagination".
         */

        const pagination =
            document.getElementById('pagination');


        if (!pagination) {

            console.error(
                'Елемент #pagination не знайдено.'
            );

            return;
        }


        /*
         * Remove only old buttons/content.
         */

        pagination.innerHTML = '';


        /*
         * Add pagination class.
         */

        pagination.className =
            'pagination';


        /* =====================================================
         * Previous / Back button
         * ===================================================== */

        const previousButton =
            document.createElement('button');


        previousButton.type =
            'button';


        previousButton.className =
            'pagination__button';


        /*
         * English text + left arrow.
         */

        previousButton.textContent =
            '← Back';


        /*
         * IMPORTANT:
         *
         * has_previous === true
         *     -> button enabled
         *
         * has_previous === false
         *     -> button disabled
         */

        previousButton.disabled =
            !paginationData.has_previous;


        /*
         * Explicit class for visual state.
         *
         * This makes the state clear in CSS.
         */

        previousButton.classList.toggle(
            'pagination__button--disabled',
            !paginationData.has_previous
        );


        previousButton.classList.toggle(
            'pagination__button--active',
            paginationData.has_previous
        );


        /*
         * Click handler.
         */

        previousButton.addEventListener(
            'click',
            async () => {

                /*
                 * Safety check.
                 *
                 * Even if somebody triggers the event manually,
                 * we do not request the previous page when
                 * backend says there is no previous page.
                 */

                if (!paginationData.has_previous) {
                    return;
                }


                page =
                    Number(paginationData.page) - 1;


                await displayFiles();
            }
        );


        /* =====================================================
         * Current page
         * ===================================================== */

        const pageNumber =
            document.createElement('span');


        pageNumber.className =
            'pagination__page';


        pageNumber.textContent =
            `Page ${paginationData.page} ` +
            `of ${paginationData.total_pages}`;


        /* =====================================================
         * Next button
         * ===================================================== */

        const nextButton =
            document.createElement('button');


        nextButton.type =
            'button';


        nextButton.className =
            'pagination__button';


        /*
         * English text + right arrow.
         */

        nextButton.textContent =
            'Next →';


        /*
         * IMPORTANT:
         *
         * has_next === true
         *     -> button enabled
         *
         * has_next === false
         *     -> button disabled
         */

        nextButton.disabled =
            !paginationData.has_next;


        /*
         * Explicit class for visual state.
         */

        nextButton.classList.toggle(
            'pagination__button--disabled',
            !paginationData.has_next
        );


        nextButton.classList.toggle(
            'pagination__button--active',
            paginationData.has_next
        );


        /*
         * Click handler.
         */

        nextButton.addEventListener(
            'click',
            async () => {

                /*
                 * Safety check.
                 */

                if (!paginationData.has_next) {
                    return;
                }


                page =
                    Number(paginationData.page) + 1;


                await displayFiles();
            }
        );


        /* =====================================================
         * Assemble pagination
         * ===================================================== */

        pagination.appendChild(
            previousButton
        );


        pagination.appendChild(
            pageNumber
        );


        pagination.appendChild(
            nextButton
        );
    };


    /* =========================================================
     * Display files
     * ========================================================= */

    const displayFiles = async () => {

        if (!fileListWrapper) {

            console.error(
                'Елемент #file-list-wrapper не знайдено.'
            );

            return;
        }


        console.log(
            `[UI] Requesting images list. Page: ${page}`
        );


        /* =====================================================
         * Loading
         * ===================================================== */

        fileListWrapper.innerHTML = `
            <p
                class="upload__promt"
                style="text-align: center; margin-top: 50px;"
            >
                Loading...
            </p>
        `;


        /*
         * Request data from backend.
         */

        const data =
            await getImages();


        /*
         * Request failed.
         */

        if (data === null) {
            return;
        }


        /*
         * Extract items and pagination.
         */

        const files =
            data.items;


        const paginationData =
            data.pagination;


        /*
         * Clear old file content.
         *
         * #pagination is outside #file-list-wrapper,
         * so it will NOT be removed.
         */

        fileListWrapper.innerHTML = '';


        /* =====================================================
         * No images
         * ===================================================== */

        if (files.length === 0) {

            fileListWrapper.innerHTML = `
                <p
                    class="upload__promt"
                    style="text-align: center; margin-top: 50px;"
                >
                    No images yet.
                </p>
            `;


            updateTabStyles();


            /*
             * Render pagination even when
             * items array is empty.
             */

            renderPagination(
                paginationData
            );


            return;
        }


        /* =====================================================
         * List container
         * ===================================================== */

        const container =
            document.createElement('div');


        container.className =
            'file-list-container';


        /* =====================================================
         * Header
         * ===================================================== */

        const header =
            document.createElement('div');


        header.className =
            'file-list-header';


        header.innerHTML = `
            <div class="file-col file-col-name">
                Name
            </div>

            <div class="file-col file-col-url">
                Url
            </div>

            <div class="file-col file-col-delete">
                Delete
            </div>
        `;


        container.appendChild(
            header
        );


        /* =====================================================
         * File list
         * ===================================================== */

        const list =
            document.createElement('div');


        list.id =
            'file-list';


        files.forEach((fileData) => {

            /* =================================================
             * Validate object
             * ================================================= */

            if (
                !fileData ||
                typeof fileData !== 'object'
            ) {

                console.warn(
                    '[UI] Некоректний запис пропущено:',
                    fileData
                );

                return;
            }


            /* =================================================
             * Validate ID
             * ================================================= */

            if (
                fileData.id === undefined ||
                fileData.id === null
            ) {

                console.warn(
                    '[UI] У зображення відсутній id:',
                    fileData
                );

                return;
            }


            /* =================================================
             * Validate filename
             * ================================================= */

            if (!fileData.filename) {

                console.warn(
                    '[UI] У зображення відсутній filename:',
                    fileData
                );

                return;
            }


            /* =================================================
             * File row
             * ================================================= */

            const fileItem =
                document.createElement('div');


            fileItem.className =
                'file-list-item';


            /* =================================================
             * Name column
             * ================================================= */

            const nameColumn =
                document.createElement('div');


            nameColumn.className =
                'file-col file-col-name';


            const fileIcon =
                document.createElement('span');


            fileIcon.className =
                'file-icon';


            const image =
                document.createElement('img');


            const imageUrl =
                `${API_BASE_URL}/images/` +
                encodeURIComponent(
                    fileData.filename
                );


            image.src =
                imageUrl;


            image.width =
                100;


            image.height =
                100;


            const originalName =
                fileData.original_name ||
                fileData.filename;


            image.title =
                originalName;


            image.alt =
                originalName;


            fileIcon.appendChild(
                image
            );


            nameColumn.appendChild(
                fileIcon
            );


            /* =================================================
             * URL column
             * ================================================= */

            const urlColumn =
                document.createElement('div');


            urlColumn.className =
                'file-col file-col-url';


            urlColumn.textContent =
                imageUrl;


            /* =================================================
             * Delete column
             * ================================================= */

            const deleteColumn =
                document.createElement('div');


            deleteColumn.className =
                'file-col file-col-delete';


            const deleteButton =
                document.createElement('button');


            deleteButton.type =
                'button';


            deleteButton.className =
                'delete-btn';


            deleteButton.dataset.id =
                String(fileData.id);


            const deleteImage =
                document.createElement('img');


            deleteImage.src =
                '../image-uploader/img/icon/delete.png';


            deleteImage.alt =
                'delete icon';


            deleteButton.appendChild(
                deleteImage
            );


            deleteColumn.appendChild(
                deleteButton
            );


            /* =================================================
             * Assemble row
             * ================================================= */

            fileItem.appendChild(
                nameColumn
            );


            fileItem.appendChild(
                urlColumn
            );


            fileItem.appendChild(
                deleteColumn
            );


            list.appendChild(
                fileItem
            );
        });


        container.appendChild(
            list
        );


        fileListWrapper.appendChild(
            container
        );


        /* =====================================================
         * Pagination
         * ===================================================== */

        renderPagination(
            paginationData
        );


        updateTabStyles();


        console.log(
            `[UI] Images displayed: ${files.length}. ` +
            `Page: ${paginationData.page}/` +
            `${paginationData.total_pages}`
        );
    };


    /* =========================================================
     * Delete image
     *
     * DELETE /delete/{id}
     * ========================================================= */

    const deleteFile = async (imageId) => {

        if (
            imageId === undefined ||
            imageId === null ||
            imageId === ''
        ) {

            alert(
                'Помилка видалення: не вказано ID зображення.'
            );

            return;
        }


        try {

            console.log(
                `[API] DELETE /delete/${imageId}`
            );


            const response = await fetch(
                `${API_BASE_URL}/delete/` +
                `${encodeURIComponent(imageId)}`,
                {
                    method: 'DELETE'
                }
            );


            console.log(
                '[API] /delete response:',
                response.status
            );


            if (!response.ok) {

                throw new Error(
                    `Сервер повернув HTTP ${response.status}`
                );
            }


            const responseText =
                await response.text();


            console.log(
                '[API] /delete body:',
                responseText
            );


            /*
             * If response isn't empty,
             * verify valid JSON.
             */

            if (responseText.trim()) {

                try {

                    JSON.parse(
                        responseText
                    );

                } catch (error) {

                    throw new Error(
                        'Сервер повернув некоректний JSON ' +
                        'після видалення.'
                    );
                }
            }


            /*
             * Reload current page.
             *
             * Backend recalculates pagination.
             */

            await displayFiles();

        } catch (error) {

            console.error(
                '[API] Помилка видалення:',
                error
            );


            alert(
                'Помилка під час видалення зображення:\n\n' +
                error.message
            );
        }
    };


    /* =========================================================
     * Delete button handler
     * ========================================================= */

    if (fileListWrapper) {

        fileListWrapper.addEventListener(
            'click',
            async (event) => {

                /*
                 * Event delegation.
                 */

                const deleteButton =
                    event.target.closest(
                        '.delete-btn'
                    );


                if (!deleteButton) {
                    return;
                }


                const imageId =
                    deleteButton.dataset.id;


                console.log(
                    '[UI] Delete button clicked. ID:',
                    imageId
                );


                /*
                 * Disable button while deleting.
                 */

                deleteButton.disabled =
                    true;


                await deleteFile(
                    imageId
                );
            }
        );
    }


    /* =========================================================
     * Redirect to upload.html
     * ========================================================= */

    if (uploadRedirectButton) {

        uploadRedirectButton.addEventListener(
            'click',
            () => {

                window.location.href =
                    'upload.html';
            }
        );
    }


    /* =========================================================
     * Initial page loading
     * ========================================================= */

    console.log(
        '[INIT] Images page loaded.'
    );


    updateTabStyles();


    displayFiles();
});
