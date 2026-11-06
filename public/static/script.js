document.addEventListener('DOMContentLoaded', () => {
    // --- Elements ---
    const cleanForm = document.getElementById('cleanForm');
    const captionUrlInput = document.getElementById('captionUrl');
    const clearBtn = document.getElementById('clearBtn');
    const submitBtn = document.getElementById('submitBtn');
    const btnText = submitBtn.querySelector('.btn-text');
    const btnLoader = submitBtn.querySelector('.btn-loader');
    
    const resultsSection = document.getElementById('resultsSection');
    const statOriginal = document.getElementById('statOriginal');
    const statOriginalTokens = document.getElementById('statOriginalTokens');
    const statCleaned = document.getElementById('statCleaned');
    const statCleanedTokens = document.getElementById('statCleanedTokens');
    const statSaved = document.getElementById('statSaved');
    const statTokensSaved = document.getElementById('statTokensSaved');
    
    const outputContent = document.getElementById('outputContent');
    const copyBtn = document.getElementById('copyBtn');
    const copyBtnText = document.getElementById('copyBtnText');
    const iconCopy = copyBtn.querySelector('.icon-copy');
    const iconCheck = copyBtn.querySelector('.icon-check');
    
    const errorBanner = document.getElementById('errorBanner');
    const errorMessage = document.getElementById('errorMessage');
    
    const exampleBtn = document.getElementById('exampleBtn');

    // --- User's Example URL ---
    const SAMPLE_URL = "https://www.youtube.com/watch?v=pde1xL9D7ic";

    // --- Input Clear Button Handler ---
    captionUrlInput.addEventListener('input', () => {
        if (captionUrlInput.value.trim().length > 0) {
            clearBtn.classList.add('visible');
        } else {
            clearBtn.classList.remove('visible');
        }
    });

    clearBtn.addEventListener('click', () => {
        captionUrlInput.value = '';
        clearBtn.classList.remove('visible');
        captionUrlInput.focus();
    });

    // --- Load Sample Click ---
    exampleBtn.addEventListener('click', () => {
        captionUrlInput.value = SAMPLE_URL;
        clearBtn.classList.add('visible');
        
        // Add a micro-pulse highlight to input when loaded
        captionUrlInput.focus();
        captionUrlInput.classList.add('pulse-input');
        setTimeout(() => captionUrlInput.classList.remove('pulse-input'), 600);
    });

    // --- Submit / Fetch Form ---
    cleanForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const urlValue = captionUrlInput.value.trim();
        if (!urlValue) return;

        // Reset UI States
        errorBanner.classList.add('hidden');
        resultsSection.classList.add('hidden');
        setLoading(true);

        try {
            const response = await fetch('/api/clean', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ url: urlValue })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || `Server returned error (${response.status})`);
            }

            // Populate and Show Results
            displayResults(data);
        } catch (error) {
            console.error('Error fetching transcript:', error);
            errorMessage.textContent = error.message || 'An unexpected error occurred while processing the transcript.';
            errorBanner.classList.remove('hidden');
            errorBanner.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        } finally {
            setLoading(false);
        }
    });

    // --- Loading State Handler ---
    function setLoading(isLoading) {
        if (isLoading) {
            submitBtn.disabled = true;
            captionUrlInput.disabled = true;
            btnText.textContent = 'Processing...';
            btnLoader.classList.remove('hidden');
            submitBtn.style.opacity = '0.8';
        } else {
            submitBtn.disabled = false;
            captionUrlInput.disabled = false;
            btnText.textContent = 'Fetch & Clean';
            btnLoader.classList.add('hidden');
            submitBtn.style.opacity = '1';
        }
    }

    // --- Display Results Utility ---
    function displayResults(data) {
        // Format sizes nicely
        const originalKB = (data.stats.original_chars / 1024).toFixed(1);
        const cleanedKB = (data.stats.cleaned_chars / 1024).toFixed(1);

        // Populate text content
        outputContent.textContent = data.cleaned_text;

        // Populate metrics (with counting up effect or immediate presentation)
        animateCountValue(statOriginal, 0, originalKB, ' KB', 1);
        statOriginalTokens.textContent = `~${data.stats.original_tokens_est.toLocaleString()} tokens`;

        animateCountValue(statCleaned, 0, cleanedKB, ' KB', 1);
        statCleanedTokens.textContent = `~${data.stats.cleaned_tokens_est.toLocaleString()} tokens`;

        animateCountValue(statSaved, 0, data.stats.savings_percentage, '%', 1);
        statTokensSaved.textContent = `${data.stats.tokens_saved_est.toLocaleString()} tokens saved`;

        // Unhide section and scroll to it
        resultsSection.classList.remove('hidden');
        resultsSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    // --- Stat Counter Animation ---
    function animateCountValue(element, start, end, suffix = '', decimals = 0) {
        let startTimestamp = null;
        const duration = 800; // ms
        const targetValue = parseFloat(end);
        const startValue = parseFloat(start);

        const step = (timestamp) => {
            if (!startTimestamp) startTimestamp = timestamp;
            const progress = Math.min((timestamp - startTimestamp) / duration, 1);
            
            // Easing out quadratic function
            const easeProgress = progress * (2 - progress);
            const currentValue = startValue + easeProgress * (targetValue - startValue);
            
            element.textContent = currentValue.toFixed(decimals) + suffix;
            
            if (progress < 1) {
                window.requestAnimationFrame(step);
            } else {
                element.textContent = end + suffix; // Guarantee precise end value
            }
        };
        
        window.requestAnimationFrame(step);
    }

    // --- Copy to Clipboard Handler ---
    copyBtn.addEventListener('click', async () => {
        const textToCopy = outputContent.textContent;
        if (!textToCopy) return;

        try {
            await navigator.clipboard.writeText(textToCopy);
            
            // Success visual state transition
            copyBtn.classList.add('success');
            iconCopy.classList.add('hidden');
            iconCheck.classList.remove('hidden');
            copyBtnText.textContent = 'Copied!';

            // Reset back after 2 seconds
            setTimeout(() => {
                copyBtn.classList.remove('success');
                iconCopy.classList.remove('hidden');
                iconCheck.classList.add('hidden');
                copyBtnText.textContent = 'Copy Text';
            }, 2000);
        } catch (err) {
            console.error('Failed to copy transcript:', err);
            alert('Could not copy text automatically. Please select the text manually and copy.');
        }
    });
});
