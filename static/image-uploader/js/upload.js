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

    // Вспомогательная функция для чтения файла в DataURL через Promise
    const readFileAsDataURL = (file) => {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = (event) => resolve(event.target.result);
            reader.onerror = (error) => reject(error);
            reader.readAsDataURL(file);
        });
    };

    const handleAndStoreFiles = async (files) => {
        if (!files || files.length === 0) {
            return;
        }

        const allowedTypes = ['image/jpeg', 'image/png', 'image/gif'];
        const MAX_SIZE_MB = 5;
        const MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024;

        const formData = new FormData();
        const validFiles = [];

        // 1. Фильтруем файлы и наполняем FormData
        for (const file of files) {
            if (!allowedTypes.includes(file.type) || file.size > MAX_SIZE_BYTES) {
                console.warn(`File rejected: ${file.name}`);
                continue;
            }
            formData.append('files', file);
            validFiles.push(file);
        }

        if (validFiles.length === 0) {
            alert("Максимальний розмір завантажуваного зображення — 5 МБ");
            return;
        }

        try {
            // 2. Отправка данных на сервер
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });

            // Парсим JSON-ответ от сервера
            const resultData = await response.json();
            console.log('Server response:', resultData);

            if (!response.ok || resultData.status === 'Error') {
                console.error('Upload failed:', resultData.message);
                alert(`Error: ${resultData.message || 'Files upload failed'}`);
                return;
            }

            // 3. Получаем массив уникальных имен файлов от сервера (resultData.file)
            const serverFileNames = resultData.file || [];
            const storedFiles = JSON.parse(localStorage.getItem('uploadedImages')) || [];
            let lastServerFileName = '';

            // Проходим по каждому файлу и связываем его с уникальным именем от сервера
            for (let i = 0; i < validFiles.length; i++) {
                const file = validFiles[i];
                // Берем уникальное имя, которое прислал сервер для этого файла
                const uniqueFileName = serverFileNames[i] || file.name;

                const fileDataUrl = await readFileAsDataURL(file);

                const fileData = {
                    name: uniqueFileName, // Сохраняем уникальное имя в localStorage
                    url: fileDataUrl
                };

                storedFiles.push(fileData);
                lastServerFileName = uniqueFileName;
            }

            // Сохраняем обновленный массив в localStorage
            localStorage.setItem('uploadedImages', JSON.stringify(storedFiles));
            updateTabStyles();

            // 4. Подставляем ссылку на последний загруженный файл с учетом NGINX (порт 8080)
            if (currentUploadInput && lastServerFileName) {
                currentUploadInput.value = `http://localhost:8080/images/${lastServerFileName}`;
            }

            alert(`${resultData.message || 'Files uploaded successfully!'}`);

        } catch (error) {
            console.error('Upload network or parsing error:', error);
            alert("Error: Failed to connect to the server.");
        }
    };

    if (copyButton && currentUploadInput) {
        copyButton.addEventListener('click', () => {
            const textToCopy = currentUploadInput.value;

            if (textToCopy && textToCopy !== 'https://') {
                navigator.clipboard.writeText(textToCopy).then(() => {
                    copyButton.textContent = 'COPIED!';
                    setTimeout(() => {
                        copyButton.textContent = 'COPY';
                    }, 2000);
                }).catch(err => {
                    console.error('Failed to copy text: ', err);
                });
            }
        });
    }

    if (imagesButton) {
        imagesButton.addEventListener('click', () => {
            window.location.href = 'images.html';
        });
    }

    fileUpload.addEventListener('change', (event) => {
        handleAndStoreFiles(event.target.files);
        event.target.value = '';
    });

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
        });
    });

    dropzone.addEventListener('drop', (event) => {
        handleAndStoreFiles(event.dataTransfer.files);
    });

    updateTabStyles();
});