document.addEventListener('DOMContentLoaded', function () {
    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape' || event.key === 'F5') {
            event.preventDefault();
            sessionStorage.removeItem('pageWasVisited');
            window.location.href = '../index.html';
        }
    });
});


document.addEventListener('DOMContentLoaded', () => {

    const fileUpload = document.getElementById('file-upload');
    const imagesButton = document.getElementById('images-tab-btn');
    const dropzone = document.querySelector('.upload__dropzone');
    const currentUploadInput = document.querySelector('.upload__input');
    const copyButton = document.querySelector('.upload__copy');


    /*
     * ---------------------------------------------------------
     * Update active tab
     * ---------------------------------------------------------
     */

    const updateTabStyles = () => {
        const uploadTab = document.getElementById('upload-tab-btn');
        const imagesTab = document.getElementById('images-tab-btn');
        const isImagesPage = window.location.pathname.includes('images.html');

        uploadTab.classList.remove('upload__tab--active');
        imagesTab.classList.remove('upload__tab--active');

        if (isImagesPage) {
            imagesTab.classList.add('upload__tab--active');
        } else {
            uploadTab.classList.add('upload__tab--active');
        }
    };


    /*
     * Helper function for reading a file as DataURL using Promise.
     */

    const readFileAsDataURL = (file) => {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();

            reader.onload = (event) => {
                resolve(event.target.result);
            };

            reader.onerror = (error) => {
                reject(error);
            };

            reader.readAsDataURL(file);
        });
    };


    /*
     * Handle selected or dropped files and upload them to the server.
     */

    const handleAndStoreFiles = async (files) => {

        if (!files || files.length === 0) {
            return;
        }


        const allowedTypes = [
            'image/jpeg',
            'image/png',
            'image/gif'
        ];

        const MAX_SIZE_MB = 5;
        const MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024;


        const formData = new FormData();
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

            formData.append('files', file);
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
             * Send files to the server.
             */

            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });


            /*
             * Parse JSON response from the server.
             */

            const resultData = await response.json();

            console.log(
                'Відповідь сервера:',
                resultData
            );


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
             * Get the array of unique file names returned by the server.
             */

            const serverFileNames =
                resultData.file || [];


            const storedFiles =
                JSON.parse(
                    localStorage.getItem('uploadedImages')
                ) || [];


            let lastServerFileName = '';


            /*
             * Process each file and associate it with
             * the unique file name returned by the server.
             */

            for (
                let i = 0;
                i < validFiles.length;
                i++
            ) {

                const file = validFiles[i];


                /*
                 * Use the unique file name returned by the server.
                 */

                const uniqueFileName =
                    serverFileNames[i] || file.name;


                const fileDataUrl =
                    await readFileAsDataURL(file);


                const fileData = {

                    /*
                     * Store the unique file name in localStorage.
                     */

                    name: uniqueFileName,

                    url: fileDataUrl
                };


                storedFiles.push(fileData);

                lastServerFileName =
                    uniqueFileName;
            }


            /*
             * Save the updated array to localStorage.
             */

            localStorage.setItem(
                'uploadedImages',
                JSON.stringify(storedFiles)
            );


            updateTabStyles();


            /*
             * Set the URL of the last uploaded file.
             * NGINX is running on port 8080.
             */

            if (
                currentUploadInput &&
                lastServerFileName
            ) {

                currentUploadInput.value =
                    `http://localhost:8080/images/${lastServerFileName}`;
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
                'Помилка: не вдалося підключитися до сервера.'
            );
        }
    };


    /*
     * ---------------------------------------------------------
     * Copy URL button
     * ---------------------------------------------------------
     */

    if (copyButton && currentUploadInput) {

        copyButton.addEventListener('click', () => {

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
                    .catch(err => {

                        console.error(
                            'Не вдалося скопіювати текст:',
                            err
                        );

                        alert(
                            'Не вдалося скопіювати посилання.'
                        );
                    });
            }
        });
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

                handleAndStoreFiles(
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
                (e) => {

                    e.preventDefault();
                    e.stopPropagation();
                }
            );
        });


        /*
         * Handle dropped files.
         */

        dropzone.addEventListener(
            'drop',
            (event) => {

                handleAndStoreFiles(
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