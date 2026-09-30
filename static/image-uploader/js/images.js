document.addEventListener('DOMContentLoaded', () => {

    const API_BASE_URL = 'http://localhost:8080';
    var page = 1;

    const fileListWrapper = document.getElementById('file-list-wrapper');
    const uploadRedirectButton = document.getElementById('upload-tab-btn');


    /* images
     * ---------------------------------------------------------
     * F5 and Escape keys
     * ---------------------------------------------------------
     */

    document.addEventListener('keydown', (event) => {
        if (event.key === 'F5' || event.key === 'Escape') {
            event.preventDefault();
            window.location.href = 'upload.html';
        }
    });


    /*
     * ---------------------------------------------------------
     * Update active tab
     * ---------------------------------------------------------
     */

    const updateTabStyles = () => {
        const uploadTab = document.getElementById('upload-tab-btn');
        const imagesTab = document.getElementById('images-tab-btn');

        const isImagesPage =
            window.location.pathname.includes('images.html');

        if (uploadTab) {
            uploadTab.classList.remove('upload__tab--active');
        }

        if (imagesTab) {
            imagesTab.classList.remove('upload__tab--active');
        }

        if (isImagesPage) {
            if (imagesTab) {
                imagesTab.classList.add('upload__tab--active');
            }
        } else {
            if (uploadTab) {
                uploadTab.classList.add('upload__tab--active');
            }
        }
    };


    /*
     * ---------------------------------------------------------
     * Get images list
     *
     * GET http://localhost:8080/images-list
     * ---------------------------------------------------------
     */

    const getImages = async () => {

        try {

            console.log('[API] GET /images-list');


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
             * Read the response as text.
             *
             * This allows us to correctly handle:
             *
             * {}
             * []
             * empty response
             * invalid JSON
             */

            const responseText =
                await response.text();


            console.log(
                '[API] /images-list body:',
                responseText
            );


            /*
             * Treat an empty response as an empty list.
             */

            if (!responseText.trim()) {
                return [];
            }


            let data;


            try {

                data = JSON.parse(responseText);

            } catch (error) {

                throw new Error(
                    'Сервер повернув некоректний JSON.'
                );
            }


            /*
             * If the server returned an empty object:
             *
             * {}
             *
             * treat the result as an empty list.
             */

            if (
                data &&
                typeof data === 'object' &&
                !Array.isArray(data) &&
                Object.keys(data).length === 0
            ) {
                return [];
            }


            /*
             * Expected format:
             *
             * [
             *   {
             *      id,
             *      filename,
             *      original_name,
             *      size,
             *      upload_time,
             *      file_type
             *   }
             * ]
             */

            if (!Array.isArray(data)) {

                throw new Error(
                    'Некоректний формат відповіді. ' +
                    'Очікувався JSON-масив.'
                );
            }


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


    /*
     * ---------------------------------------------------------
     * Build images list
     * ---------------------------------------------------------
     */

    const displayFiles = async () => {

        if (!fileListWrapper) {

            console.error(
                'Елемент #file-list-wrapper не знайдено.'
            );

            return;
        }


        console.log(
            '[UI] Requesting images list...'
        );


        const files = await getImages();


        /*
         * null means that the request failed.
         *
         * getImages() has already shown an alert.
         */

        if (files === null) {
            return;
        }


        /*
         * Clear previous content.
         */

        fileListWrapper.innerHTML = '';


        /*
         * Display a message when there are no files.
         */

        if (files.length === 0) {

            fileListWrapper.innerHTML = `
                <p
                    class="upload__promt"
                    style="text-align: center; margin-top: 50px;"
                >
                    Зображень ще немає.
                </p>
            `;

            updateTabStyles();

            return;
        }


        /*
         * -----------------------------------------------------
         * List container
         * -----------------------------------------------------
         */

        const container =
            document.createElement('div');

        container.className =
            'file-list-container';


        /*
         * -----------------------------------------------------
         * Header
         * -----------------------------------------------------
         */

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


        container.appendChild(header);


        /*
         * -----------------------------------------------------
         * File list
         * -----------------------------------------------------
         */

        const list =
            document.createElement('div');

        list.id = 'file-list';


        files.forEach((fileData) => {

            /*
             * Validate the object.
             */

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


            /*
             * Validate the ID.
             */

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


            /*
             * Validate the filename.
             */

            if (!fileData.filename) {

                console.warn(
                    '[UI] У зображення відсутній filename:',
                    fileData
                );

                return;
            }


            /*
             * -------------------------------------------------
             * File row
             * -------------------------------------------------
             */

            const fileItem =
                document.createElement('div');

            fileItem.className =
                'file-list-item';


            /*
             * -------------------------------------------------
             * Name
             * -------------------------------------------------
             */

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
                encodeURIComponent(fileData.filename);


            image.src = imageUrl;

            image.width = 100;

            image.height = 100;


            const originalName =
                fileData.original_name ||
                fileData.filename;


            image.title = originalName;

            image.alt = originalName;


            fileIcon.appendChild(image);

            nameColumn.appendChild(fileIcon);


            /*
             * -------------------------------------------------
             * URL
             * -------------------------------------------------
             */

            const urlColumn =
                document.createElement('div');

            urlColumn.className =
                'file-col file-col-url';


            urlColumn.textContent =
                imageUrl;


            /*
             * -------------------------------------------------
             * Delete
             * -------------------------------------------------
             */

            const deleteColumn =
                document.createElement('div');

            deleteColumn.className =
                'file-col file-col-delete';


            const deleteButton =
                document.createElement('button');

            deleteButton.type = 'button';

            deleteButton.className =
                'delete-btn';


            /*
             * Database record ID.
             */

            deleteButton.dataset.id =
                String(fileData.id);


            const deleteImage =
                document.createElement('img');

            deleteImage.src =
                '../image-uploader/img/icon/delete.png';

            deleteImage.alt =
                'delete icon';


            deleteButton.appendChild(deleteImage);

            deleteColumn.appendChild(deleteButton);


            /*
             * -------------------------------------------------
             * Assemble the row
             * -------------------------------------------------
             */

            fileItem.appendChild(nameColumn);

            fileItem.appendChild(urlColumn);

            fileItem.appendChild(deleteColumn);


            list.appendChild(fileItem);
        });


        container.appendChild(list);

        fileListWrapper.appendChild(container);


        updateTabStyles();


        console.log(
            `[UI] Images displayed: ${files.length}`
        );
    };


    /*
     * ---------------------------------------------------------
     * Delete image
     *
     * DELETE /delete/{id}
     * ---------------------------------------------------------
     */

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
                `${API_BASE_URL}/delete/${encodeURIComponent(imageId)}`,
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


            /*
             * The server may return:
             *
             * {}
             * []
             * JSON
             * empty response
             */

            const responseText =
                await response.text();


            console.log(
                '[API] /delete body:',
                responseText
            );


            /*
             * If the response is not empty,
             * verify that it contains valid JSON.
             */

            if (responseText.trim()) {

                try {

                    JSON.parse(responseText);

                } catch (error) {

                    throw new Error(
                        'Сервер повернув некоректний JSON ' +
                        'після видалення.'
                    );
                }
            }


            /*
             * Deletion completed successfully.
             *
             * Reload the updated list.
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


    /*
     * ---------------------------------------------------------
     * Delete button handler
     *
     * Event delegation is used.
     * ---------------------------------------------------------
     */

    if (fileListWrapper) {

        fileListWrapper.addEventListener(
            'click',
            async (event) => {

                /*
                 * The click may occur directly on the
                 * button or on the image inside the button.
                 */

                const deleteButton =
                    event.target.closest('.delete-btn');


                if (!deleteButton) {
                    return;
                }


                /*
                 * Get the image ID.
                 */

                const imageId =
                    deleteButton.dataset.id;


                console.log(
                    '[UI] Delete button clicked. ID:',
                    imageId
                );


                /*
                 * Disable the button while the request is running.
                 */

                deleteButton.disabled = true;


                await deleteFile(imageId);
            }
        );
    }


    /*
     * ---------------------------------------------------------
     * Redirect to upload.html
     * ---------------------------------------------------------
     */

    if (uploadRedirectButton) {

        uploadRedirectButton.addEventListener(
            'click',
            () => {

                window.location.href =
                    'upload.html';
            }
        );
    }

    /*
     * ---------------------------------------------------------
     * Initial list loading
     *
     * GET http://localhost:8080/images-list
     * ---------------------------------------------------------
     */

    console.log(
        '[INIT] Images page loaded.'
    );
    updateTabStyles();
    displayFiles();
});