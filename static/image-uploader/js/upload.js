document.addEventListener('DOMContentLoaded', function () {

    document.addEventListener('keydown', function (event) {

        if (
            event.key === 'Escape' ||
            event.key === 'F5'
        ) {

            event.preventDefault();

            window.location.href =
                '../index.html';
        }
    });
});


document.addEventListener('DOMContentLoaded', () => {

    const fileUpload =
        document.getElementById('file-upload');

    const imagesButton =
        document.getElementById('images-tab-btn');

    const dropzone =
        document.querySelector('.upload__dropzone');

    const currentUploadInput =
        document.querySelector('.upload__input');

    const copyButton =
        document.querySelector('.upload__copy');


    /*
     * ---------------------------------------------------------
     * Update active tab
     * ---------------------------------------------------------
     */

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


    /*
     * ---------------------------------------------------------
     * Handle selected or dropped files
     * ---------------------------------------------------------
     */

    const handleFiles = async (files) => {

        if (!files || files.length === 0) {
            return;
        }


        const allowedTypes = [
            'image/jpeg',
            'image/png',
            'image/gif'
        ];


        const MAX_SIZE_MB = 5;

        const MAX_SIZE_BYTES =
            MAX_SIZE_MB * 1024 * 1024;


        const formData =
            new FormData();


        const validFiles = [];


        /*
         * Filter files and populate FormData.
         */

        for (const file of files) {

            if (
                !allowedTypes.includes(file.type) ||
                file.size > MAX_SIZE_BYTES
            ) {

                console.warn(
                    `Файл відхилено: ${file.name}`
                );

                continue;
            }


            formData.append(
                'files',
                file
            );


            validFiles.push(file);
        }


        if (validFiles.length === 0) {

            alert(
                'Помилка: допустимі лише зображення JPG, PNG або GIF ' +
                'розміром не більше 5 МБ.'
            );

            return;
        }


        try {

            /*
             * -------------------------------------------------
             * Send files to the server
             * -------------------------------------------------
             */

            const response =
                await fetch(
                    '/upload',
                    {
                        method: 'POST',
                        body: formData
                    }
                );


            /*
             * Read the server response.
             */

            const responseText =
                await response.text();


            let resultData;


            /*
             * Parse the JSON response.
             */

            try {

                resultData =
                    responseText.trim()
                        ? JSON.parse(responseText)
                        : {};

            } catch (error) {

                throw new Error(
                    'Сервер повернув некоректний JSON.'
                );
            }


            console.log(
                'Відповідь сервера:',
                resultData
            );


            /*
             * Check the server response.
             */

            if (
                !response.ok ||
                resultData.status === 'Error'
            ) {

                console.error(
                    'Помилка завантаження:',
                    resultData.message
                );


                alert(
                    `Помилка: ${
                        resultData.message ||
                        'Не вдалося завантажити файли.'
                    }`
                );


                return;
            }


            /*
             * Get unique file names returned by the server.
             */

            const serverFileNames =
                Array.isArray(resultData.file)
                    ? resultData.file
                    : [];


            /*
             * Get the last uploaded file name.
             */

            const lastServerFileName =
                serverFileNames.length > 0
                    ? serverFileNames[
                        serverFileNames.length - 1
                    ]
                    : '';


            /*
             * Update the active tab.
             */

            updateTabStyles();


            /*
             * Set the URL of the last uploaded file.
             */

            if (
                currentUploadInput &&
                lastServerFileName
            ) {

                currentUploadInput.value =
                    `http://localhost:8080/images/${encodeURIComponent(
                        lastServerFileName
                    )}`;
            }


            alert(
                resultData.message ||
                'Файли успішно завантажено!'
            );


        } catch (error) {

            console.error(
                'Помилка мережі або обробки відповіді:',
                error
            );


            alert(
                `Помилка: ${
                    error.message ||
                    'Не вдалося підключитися до сервера.'
                }`
            );
        }
    };


    /*
     * ---------------------------------------------------------
     * Copy URL button
     * ---------------------------------------------------------
     */

    if (
        copyButton &&
        currentUploadInput
    ) {

        copyButton.addEventListener(
            'click',
            () => {

                const textToCopy =
                    currentUploadInput.value;


                if (
                    textToCopy &&
                    textToCopy !== 'https://'
                ) {

                    navigator.clipboard
                        .writeText(textToCopy)

                        .then(() => {

                            copyButton.textContent =
                                'СКОПІЙОВАНО!';


                            setTimeout(() => {

                                copyButton.textContent =
                                    'КОПІЮВАТИ';

                            }, 2000);
                        })

                        .catch(error => {

                            console.error(
                                'Не вдалося скопіювати текст:',
                                error
                            );


                            alert(
                                'Не вдалося скопіювати посилання.'
                            );
                        });
                }
            }
        );
    }


    /*
     * ---------------------------------------------------------
     * Navigate to images page
     * ---------------------------------------------------------
     */

    if (imagesButton) {

        imagesButton.addEventListener(
            'click',
            () => {

                window.location.href =
                    'images.html';
            }
        );
    }


    /*
     * ---------------------------------------------------------
     * Handle file selection
     * ---------------------------------------------------------
     */

    if (fileUpload) {

        fileUpload.addEventListener(
            'change',
            (event) => {

                handleFiles(
                    event.target.files
                );


                event.target.value = '';
            }
        );
    }


    /*
     * ---------------------------------------------------------
     * Prevent default drag-and-drop browser behavior
     * ---------------------------------------------------------
     */

    if (dropzone) {

        [
            'dragenter',
            'dragover',
            'dragleave',
            'drop'
        ].forEach(eventName => {

            dropzone.addEventListener(
                eventName,
                (event) => {

                    event.preventDefault();
                    event.stopPropagation();
                }
            );
        });


        /*
         * Handle dropped files.
         */

        dropzone.addEventListener(
            'drop',
            (event) => {

                handleFiles(
                    event.dataTransfer.files
                );
            }
        );
    }


    /*
     * ---------------------------------------------------------
     * Initialize active tab
     * ---------------------------------------------------------
     */
    updateTabStyles();
});