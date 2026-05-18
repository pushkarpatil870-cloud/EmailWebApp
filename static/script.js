document.addEventListener('DOMContentLoaded', function() {
    
    // --- 1. Sidebar Toggle Setup ---
    const wrapper = document.getElementById('wrapper');
    const menuToggle = document.getElementById('menu-toggle');
    if (menuToggle && wrapper) {
        menuToggle.addEventListener('click', e => {
            e.preventDefault();
            wrapper.classList.toggle('toggled');
        });
    }

    // --- 2. Dark/Light Mode Theme Toggle Setup ---
    const themeToggleBtn = document.getElementById('themeToggle');
    const htmlElement = document.documentElement;
    const savedTheme = localStorage.getItem('mailflow_theme') || 'light';
    htmlElement.setAttribute('data-bs-theme', savedTheme);
    
    if (themeToggleBtn) {
        // Set initial icon
        themeToggleBtn.innerHTML = savedTheme === 'dark' ? '<i class="fas fa-sun text-warning me-1"></i>Theme' : '<i class="fas fa-moon text-muted me-1"></i>Theme';
        
        themeToggleBtn.addEventListener('click', () => {
            let current = htmlElement.getAttribute('data-bs-theme');
            let next = current === 'light' ? 'dark' : 'light';
            htmlElement.setAttribute('data-bs-theme', next);
            localStorage.setItem('mailflow_theme', next);
            themeToggleBtn.innerHTML = next === 'dark' ? '<i class="fas fa-sun text-warning me-1"></i>Theme' : '<i class="fas fa-moon text-muted me-1"></i>Theme';
        });
    }

    // --- 3. Reusable Password Visibility Eye Toggle ---
    const toggleButtons = document.querySelectorAll('.toggle-password-btn');
    toggleButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetId = btn.getAttribute('data-target');
            const targetInput = document.getElementById(targetId);
            if (targetInput) {
                const isPassword = targetInput.getAttribute('type') === 'password';
                targetInput.setAttribute('type', isPassword ? 'text' : 'password');
                
                // Toggle eye icon class
                const icon = btn.querySelector('i');
                if (icon) {
                    icon.classList.toggle('fa-eye', !isPassword);
                    icon.classList.toggle('fa-eye-slash', isPassword);
                }
            }
        });
    });

    // --- 3.1 Convert UTC dates to local browser timezone ---
    const dateElements = document.querySelectorAll('.format-date');
    dateElements.forEach(el => {
        const utcDateStr = el.getAttribute('data-utc');
        if (utcDateStr) {
            const dateObj = new Date(utcDateStr);
            if (!isNaN(dateObj.getTime())) {
                const year = dateObj.getFullYear();
                const month = String(dateObj.getMonth() + 1).padStart(2, '0');
                const day = String(dateObj.getDate()).padStart(2, '0');
                const hours = String(dateObj.getHours()).padStart(2, '0');
                const minutes = String(dateObj.getMinutes()).padStart(2, '0');
                el.textContent = `${year}-${month}-${day} ${hours}:${minutes}`;
            }
        }
    });

    // --- 4. Quill Rich Text Editor Setup ---
    const editorEl = document.getElementById('editor');
    let quill;
    if (editorEl) {
        quill = new Quill('#editor', {
            theme: 'snow',
            placeholder: 'Write your email here...',
            modules: {
                toolbar: [
                    ['bold', 'italic', 'underline', 'strike'],
                    [{ 'list': 'ordered'}, { 'list': 'bullet' }],
                    [{ 'header': [1, 2, 3, false] }],
                    [{ 'color': [] }, { 'background': [] }],
                    ['link', 'clean']
                ]
            }
        });

        // Live Character Counter
        const charCounter = document.getElementById('char-counter');
        quill.on('text-change', function() {
            const text = quill.getText().trim();
            charCounter.textContent = text === "" ? 0 : text.length;
        });

        // intercept compose submission
        const composeForm = document.getElementById('composeForm');
        if (composeForm) {
            composeForm.addEventListener('submit', function(e) {
                // Transfer Quill HTML contents to hidden textarea
                document.getElementById('body-hidden').value = quill.root.innerHTML;
                
                // Show loader if it's sending (not draft)
                const activeBtn = document.activeElement;
                if (activeBtn && activeBtn.value === 'send') {
                    // Confirmation popup
                    if(!confirm('Are you sure you want to send this email now?')) {
                        e.preventDefault();
                        return;
                    }
                    document.getElementById('sendBtn').classList.add('disabled');
                    document.getElementById('loadingSpinner').classList.remove('d-none');
                }
            });
        }
    }

    // --- 5. Drag and Drop File Upload ---
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('attachments');
    const fileList = document.getElementById('file-list');

    if (dropZone && fileInput) {
        // Prevent default browser drag/drop behavior
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, preventDefaults, false);
        });

        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }

        // Highlight dropping zone
        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => dropZone.classList.add('dragover'), false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => dropZone.classList.remove('dragover'), false);
        });

        // Handle drop event
        dropZone.addEventListener('drop', (e) => {
            const dt = e.dataTransfer;
            const files = dt.files;
            fileInput.files = files; 
            updateFileList(files);
        });

        // Click zone trigger input file browse
        dropZone.addEventListener('click', () => {
            fileInput.click();
        });

        fileInput.addEventListener('change', function() {
            updateFileList(this.files);
        });

        function updateFileList(files) {
            fileList.innerHTML = '';
            Array.from(files).forEach(file => {
                const span = document.createElement('span');
                span.className = 'badge bg-primary bg-opacity-25 text-primary rounded-pill p-2 border border-primary border-opacity-25';
                span.innerHTML = `<i class="fas fa-file me-1"></i> ${file.name} <small class="text-muted ms-1">(${Math.round(file.size/1024)}kb)</small>`;
                fileList.appendChild(span);
            });
        }
    }

    // --- 6. Live Search Filter in History Page ---
    const searchInput = document.getElementById('searchInput');
    const historyTable = document.getElementById('historyTable');
    if (searchInput && historyTable) {
        searchInput.addEventListener('keyup', function() {
            const filter = this.value.toLowerCase();
            const rows = historyTable.getElementsByTagName('tbody')[0].getElementsByTagName('tr');
            
            for (let i = 0; i < rows.length; i++) {
                const text = rows[i].textContent.toLowerCase();
                // If query is found, keep row visible, else hide it
                if (text.indexOf(filter) > -1) {
                    rows[i].style.display = "";
                } else {
                    rows[i].style.display = "none";
                }
            }
        });
    }
});
