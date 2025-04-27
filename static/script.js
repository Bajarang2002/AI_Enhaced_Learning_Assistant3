document.addEventListener('DOMContentLoaded', () => {
    const uploadForm = document.querySelector('#uploadForm');
    
    if (uploadForm) {
        uploadForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const fileInput = document.querySelector('#file-upload');
            if (fileInput.files.length > 0) {
                alert(`File "${fileInput.files[0].name}" uploaded successfully!`);
            } else {
                alert('Please select a file.');
            }
        });
    }
});
