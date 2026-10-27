/**
 * =========================================================
 * SMART ATTENDANCE SYSTEM
 * Complete Frontend JavaScript
 * =========================================================
 */

"use strict";

/* =========================================================
   CONFIG
========================================================= */

const CONFIG = {
    REGISTRATION_TOTAL_SAMPLES: 5,

    RECOGNITION_INTERVAL_MS: 2500,
    VERIFICATION_SYNC_INTERVAL_MS: 10000,

    GRACE_PERIOD_MS: 7000,
    MAX_RECOGNITION_ERRORS: 5,

    CAMERA: {
        video: {
            facingMode: "user",
            width: { ideal: 640 },
            height: { ideal: 480 }
        },
        audio: false
    }
};


/* =========================================================
   GLOBAL STATE
========================================================= */

const STATE = {

    registration: {
        studentId: null,
        name: null,
        rollNo: null,
        currentSample: 0,
        totalSamples: CONFIG.REGISTRATION_TOTAL_SAMPLES,
        captured: 0,
        running: false,
        stream: null
    },

    attendance: {
        running: false,
        starting: false,

        stream: null,

        lectureId: null,
        lectureName: null,
        lectureStart: null,
        lectureEnd: null,
        requiredPercentage: 90,

        currentStudentId: null,
        currentStudentName: null,

        verifiedSeconds: 0,
        requiredSeconds: 0,

        recognitionTimer: null,
        verificationTimer: null,
        clockTimer: null,

        recognitionErrors: 0,
        lastRecognitionTime: null,

        verificationStarted: false,

        recognitionInProgress: false
    },

    lecture: null
};


/* =========================================================
   BASIC HELPERS
========================================================= */

function $(id) {
    return document.getElementById(id);
}


function showElement(element) {
    if (element) {
        element.style.display = "";
    }
}


function hideElement(element) {
    if (element) {
        element.style.display = "none";
    }
}


function setText(element, text) {
    if (element) {
        element.textContent = text ?? "";
    }
}


function safeNumber(value, fallback = 0) {
    const n = Number(value);
    return Number.isFinite(n) ? n : fallback;
}


function formatSeconds(seconds) {

    seconds = Math.max(
        0,
        Math.floor(
            safeNumber(seconds)
        )
    );

    const minutes =
        Math.floor(seconds / 60);

    const remaining =
        seconds % 60;

    return (
        `${String(minutes).padStart(2, "0")}:` +
        `${String(remaining).padStart(2, "0")}`
    );
}


function getJSONHeaders() {

    return {
        "Content-Type": "application/json"
    };
}


/* =========================================================
   MESSAGE HELPERS
========================================================= */

function setAttendanceMessage(
    message,
    type = "info"
) {

    const el =
        $("attendanceMessage");

    if (!el) {
        console.log(
            "[Attendance]",
            message
        );
        return;
    }

    el.textContent =
        message || "";

    el.classList.remove(
        "success",
        "error",
        "warning",
        "info"
    );

    el.classList.add(type);
}


function setRegistrationMessage(
    message,
    type = "info"
) {

    const el =
        $("registrationMessage");

    if (!el) return;

    el.textContent =
        message || "";

    el.classList.remove(
        "success",
        "error",
        "warning",
        "info"
    );

    el.classList.add(type);
}


/* =========================================================
   CAMERA
========================================================= */

async function openCamera(videoElement) {

    if (!videoElement) {
        throw new Error(
            "Camera element not found."
        );
    }

    if (
        !navigator.mediaDevices ||
        !navigator.mediaDevices.getUserMedia
    ) {
        throw new Error(
            "Camera access is not supported by this browser."
        );
    }

    /*
     * Stop old camera stream.
     */
    if (videoElement.srcObject) {

        stopVideoStream(
            videoElement.srcObject
        );

        videoElement.srcObject = null;
    }

    try {

        console.log(
            "[Camera] Requesting camera permission..."
        );

        setAttendanceMessage(
            "Requesting camera access...",
            "info"
        );

        const stream =
            await navigator.mediaDevices.getUserMedia(
                CONFIG.CAMERA
            );

        console.log(
            "[Camera] Camera permission granted."
        );

        videoElement.srcObject =
            stream;

        videoElement.muted =
            true;

        videoElement.playsInline =
            true;

        /*
         * Some browsers need explicit play().
         */
        try {

            await videoElement.play();

        } catch (playError) {

            console.warn(
                "[Camera] First play attempt failed:",
                playError
            );

            /*
             * Try again after metadata loads.
             */
            await new Promise(
                resolve => {

                    const handler =
                        async function () {

                            videoElement.removeEventListener(
                                "loadedmetadata",
                                handler
                            );

                            try {
                                await videoElement.play();
                            } catch (e) {
                                console.warn(
                                    "[Camera] Second play failed:",
                                    e
                                );
                            }

                            resolve();
                        };

                    videoElement.addEventListener(
                        "loadedmetadata",
                        handler
                    );

                    /*
                     * If metadata already exists.
                     */
                    if (
                        videoElement.readyState >= 1
                    ) {
                        handler();
                    }
                }
            );
        }

        /*
         * Wait briefly until actual video frames exist.
         */
        await waitForVideoReady(
            videoElement
        );

        console.log(
            "[Camera] Video stream ready.",
            videoElement.videoWidth,
            videoElement.videoHeight
        );

        return stream;

    } catch (error) {

        console.error(
            "[Camera] Error:",
            error
        );

        if (
            error.name ===
            "NotAllowedError"
        ) {

            throw new Error(
                "Camera permission denied. Please allow camera access in the browser and try again."
            );
        }

        if (
            error.name ===
            "PermissionDeniedError"
        ) {

            throw new Error(
                "Camera permission denied. Please allow camera access in the browser."
            );
        }

        if (
            error.name ===
            "NotFoundError"
        ) {

            throw new Error(
                "No camera was found on this device."
            );
        }

        if (
            error.name ===
            "NotReadableError"
        ) {

            throw new Error(
                "Camera is already being used by another application."
            );
        }

        if (
            error.name ===
            "OverconstrainedError"
        ) {

            throw new Error(
                "Camera does not support the requested settings."
            );
        }

        throw new Error(
            error.message ||
            "Unable to open camera. Please check camera permission."
        );
    }
}


function waitForVideoReady(videoElement) {

    return new Promise(
        resolve => {

            /*
             * Already ready.
             */
            if (
                videoElement.readyState >=
                    HTMLMediaElement.HAVE_CURRENT_DATA &&
                videoElement.videoWidth > 0
            ) {

                resolve();
                return;
            }

            let finished =
                false;

            const finish =
                function () {

                    if (finished) {
                        return;
                    }

                    finished = true;

                    videoElement.removeEventListener(
                        "loadeddata",
                        finish
                    );

                    videoElement.removeEventListener(
                        "canplay",
                        finish
                    );

                    resolve();
                };

            videoElement.addEventListener(
                "loadeddata",
                finish
            );

            videoElement.addEventListener(
                "canplay",
                finish
            );

            /*
             * Safety timeout.
             */
            setTimeout(
                finish,
                3000
            );
        }
    );
}


function stopVideoStream(stream) {

    if (!stream) {
        return;
    }

    try {

        stream
            .getTracks()
            .forEach(
                track => track.stop()
            );

    } catch (error) {

        console.warn(
            "Stream stop error:",
            error
        );
    }
}


function stopCamera(videoElement) {

    if (!videoElement) {
        return;
    }

    if (videoElement.srcObject) {

        stopVideoStream(
            videoElement.srcObject
        );

        videoElement.srcObject =
            null;
    }
}


/* =========================================================
   CANVAS FRAME CAPTURE
========================================================= */

function captureFrame(
    videoElement,
    canvasElement
) {

    if (
        !videoElement ||
        !canvasElement
    ) {
        return null;
    }

    if (
        videoElement.readyState <
            HTMLMediaElement.HAVE_CURRENT_DATA ||
        videoElement.videoWidth === 0 ||
        videoElement.videoHeight === 0
    ) {
        return null;
    }

    canvasElement.width =
        videoElement.videoWidth;

    canvasElement.height =
        videoElement.videoHeight;

    const ctx =
        canvasElement.getContext("2d");

    if (!ctx) {
        return null;
    }

    ctx.drawImage(
        videoElement,
        0,
        0,
        canvasElement.width,
        canvasElement.height
    );

    return canvasElement.toDataURL(
        "image/jpeg",
        0.85
    );
}


/* =========================================================
   REGISTRATION
========================================================= */

function initializeRegistration() {

    const video =
        $("registrationCamera");

    if (!video) {
        return;
    }

    console.log(
        "Registration page detected."
    );

    const startButton =
        $("startRegistrationBtn");

    const captureButton =
        $("captureSampleBtn");

    const stopButton =
        $("stopRegistrationBtn");

    if (startButton) {

        startButton.addEventListener(
            "click",
            startRegistrationCamera
        );
    }

    if (captureButton) {

        captureButton.addEventListener(
            "click",
            captureRegistrationSample
        );
    }

    if (stopButton) {

        stopButton.addEventListener(
            "click",
            stopRegistrationCamera
        );
    }

    updateRegistrationUI();
}


async function startRegistrationCamera() {

    const video =
        $("registrationCamera");

    if (!video) {
        return;
    }

    try {

        STATE.registration.running =
            true;

        STATE.registration.stream =
            await openCamera(video);

        const startButton =
            $("startRegistrationBtn");

        const captureButton =
            $("captureSampleBtn");

        const stopButton =
            $("stopRegistrationBtn");

        hideElement(startButton);
        showElement(captureButton);
        showElement(stopButton);

        setRegistrationMessage(
            "Camera started. Position your face clearly and capture the sample.",
            "info"
        );

    } catch (error) {

        STATE.registration.running =
            false;

        setRegistrationMessage(
            error.message,
            "error"
        );
    }
}


async function captureRegistrationSample() {

    if (
        !STATE.registration.running
    ) {

        setRegistrationMessage(
            "Please start the camera first.",
            "warning"
        );

        return;
    }

    const video =
        $("registrationCamera");

    const canvas =
        $("registrationCanvas");

    if (!video || !canvas) {

        setRegistrationMessage(
            "Camera or canvas element not found.",
            "error"
        );

        return;
    }

    const image =
        captureFrame(
            video,
            canvas
        );

    if (!image) {

        setRegistrationMessage(
            "Camera is not ready. Please wait a moment.",
            "warning"
        );

        return;
    }

    const studentId =
        STATE.registration.studentId ||
        $("studentId")?.value ||
        $("uid")?.value ||
        "";

    if (!studentId) {

        setRegistrationMessage(
            "Student ID/UID is missing.",
            "error"
        );

        return;
    }

    const nextSample =
        STATE.registration.captured + 1;

    try {

        setRegistrationMessage(
            `Processing sample ${nextSample}/${STATE.registration.totalSamples}...`,
            "info"
        );

        const response =
            await fetch(
                "/register-face-sample",
                {
                    method: "POST",
                    headers: getJSONHeaders(),

                    body: JSON.stringify({
                        student_id:
                            String(studentId),

                        image:
                            image,

                        sample_index:
                            nextSample
                    })
                }
            );

        const result =
            await response.json();

        if (
            !response.ok ||
            !result.success
        ) {

            throw new Error(
                result.message ||
                "Failed to save face sample."
            );
        }

        STATE.registration.captured++;

        updateRegistrationUI();

        if (
            STATE.registration.captured >=
            STATE.registration.totalSamples
        ) {

            await finalizeRegistration();

            return;
        }

        setRegistrationMessage(
            `Sample ${STATE.registration.captured}/${STATE.registration.totalSamples} captured successfully. Change your face angle slightly and capture again.`,
            "success"
        );

    } catch (error) {

        console.error(
            "Registration sample error:",
            error
        );

        setRegistrationMessage(
            error.message ||
            "Failed to capture sample.",
            "error"
        );
    }
}


async function finalizeRegistration() {

    const studentId =
        STATE.registration.studentId ||
        $("studentId")?.value ||
        $("uid")?.value ||
        "";

    if (!studentId) {

        setRegistrationMessage(
            "Student ID is missing.",
            "error"
        );

        return;
    }

    try {

        setRegistrationMessage(
            "Training face data. Please wait...",
            "info"
        );

        const response =
            await fetch(
                "/finalize-registration",
                {
                    method: "POST",
                    headers: getJSONHeaders(),

                    body: JSON.stringify({
                        student_id:
                            String(studentId)
                    })
                }
            );

        const result =
            await response.json();

        if (
            !response.ok ||
            !result.success
        ) {

            throw new Error(
                result.message ||
                "Face training failed."
            );
        }

        setRegistrationMessage(
            result.message ||
            "Face registration completed successfully.",
            "success"
        );

        stopRegistrationCamera();

        hideElement(
            $("captureSampleBtn")
        );

    } catch (error) {

        console.error(
            "Registration finalize error:",
            error
        );

        setRegistrationMessage(
            error.message ||
            "Unable to finalize registration.",
            "error"
        );
    }
}


function stopRegistrationCamera() {

    const video =
        $("registrationCamera");

    stopCamera(video);

    STATE.registration.running =
        false;

    STATE.registration.stream =
        null;

    showElement(
        $("startRegistrationBtn")
    );

    hideElement(
        $("captureSampleBtn")
    );

    hideElement(
        $("stopRegistrationBtn")
    );
}


function updateRegistrationUI() {

    const counter =
        $("sampleCounter") ||
        $("registrationCounter");

    if (counter) {

        counter.textContent =
            `${STATE.registration.captured}/${STATE.registration.totalSamples}`;
    }
}


/* =========================================================
   LECTURE HANDLING
========================================================= */

function getLectureFromSelect() {

    const select =
        $("lectureSelect");

    if (
        !select ||
        !select.value
    ) {
        return null;
    }

    const option =
        select.options[
            select.selectedIndex
        ];

    if (!option) {
        return null;
    }

    return {

        id:
            option.value,

        name:
            option.dataset.name ||
            option.textContent.trim(),

        start:
            option.dataset.start ||
            "",

        end:
            option.dataset.end ||
            "",

        required_percentage:
            safeNumber(
                option.dataset.required,
                90
            )
    };
}


function updateSelectedLectureUI(
    lecture
) {

    if (!lecture) {

        setText(
            $("selectedLectureName"),
            "No lecture selected"
        );

        setText(
            $("selectedLectureTime"),
            "--"
        );

        setText(
            $("selectedLectureRequirement"),
            "--"
        );

        return;
    }

    setText(
        $("selectedLectureName"),
        lecture.name
    );

    let time = "";

    if (
        lecture.start &&
        lecture.end
    ) {

        time =
            `${lecture.start} - ${lecture.end}`;
    }

    setText(
        $("selectedLectureTime"),
        time || "--"
    );

    setText(
        $("selectedLectureRequirement"),
        `${lecture.required_percentage}%`
    );
}


/* =========================================================
   ATTENDANCE INITIALIZATION
========================================================= */

function initializeAttendance() {

    const camera =
        $("attendanceCamera");

    const lectureSelect =
        $("lectureSelect");

    if (
        !camera &&
        !lectureSelect
    ) {
        return;
    }

    console.log(
        "Attendance page detected."
    );

    const startButton =
        $("startAttendanceBtn");

    const stopButton =
        $("stopAttendanceBtn");


    /* -----------------------------------------------------
       START BUTTON
    ----------------------------------------------------- */

    if (startButton) {

        /*
         * Prevent duplicate listener.
         */
        if (
            !startButton.dataset.attendanceBound
        ) {

            startButton.dataset.attendanceBound =
                "true";

            startButton.addEventListener(
                "click",
                async function (event) {

                    event.preventDefault();

                    console.log(
                        "[Attendance] Start Scanner clicked."
                    );

                    const lecture =
                        STATE.lecture ||
                        getLectureFromSelect();

                    if (
                        !lecture ||
                        !lecture.id
                    ) {

                        setAttendanceMessage(
                            "Please select a lecture first.",
                            "warning"
                        );

                        return;
                    }

                    await startAttendanceScanner(
                        lecture
                    );
                }
            );
        }
    }


    /* -----------------------------------------------------
       STOP BUTTON
    ----------------------------------------------------- */

    if (stopButton) {

        if (
            !stopButton.dataset.attendanceBound
        ) {

            stopButton.dataset.attendanceBound =
                "true";

            stopButton.addEventListener(
                "click",
                function (event) {

                    event.preventDefault();

                    stopAttendanceScanner();
                }
            );
        }
    }


    /* -----------------------------------------------------
       LECTURE CHANGE
    ----------------------------------------------------- */

    if (lectureSelect) {

        if (
            !lectureSelect.dataset.attendanceBound
        ) {

            lectureSelect.dataset.attendanceBound =
                "true";

            lectureSelect.addEventListener(
                "change",
                async function () {

                    const lecture =
                        getLectureFromSelect();

                    console.log(
                        "[Attendance] Lecture changed:",
                        lecture
                    );

                    if (!lecture) {

                        STATE.lecture =
                            null;

                        updateSelectedLectureUI(
                            null
                        );

                        if (startButton) {
                            startButton.disabled =
                                true;
                        }

                        setAttendanceMessage(
                            "",
                            "info"
                        );

                        return;
                    }

                    STATE.lecture =
                        lecture;

                    updateSelectedLectureUI(
                        lecture
                    );

                    if (startButton) {
                        startButton.disabled =
                            false;
                    }

                    setAttendanceMessage(
                        `Preparing camera for ${lecture.name}...`,
                        "info"
                    );

                    /*
                     * IMPORTANT:
                     * Directly call the global scanner.
                     */
                    await startAttendanceFromLectureSelection(
                        lecture
                    );
                }
            );
        }
    }


    /* -----------------------------------------------------
       EXISTING SELECTED LECTURE
       -----------------------------------------------------
       This fixes the case where attendance.html's
       inline script ran before app.js was ready.
    ----------------------------------------------------- */

    const existingLecture =
        getLectureFromSelect();

    if (existingLecture) {

        console.log(
            "[Attendance] Existing lecture found:",
            existingLecture
        );

        STATE.lecture =
            existingLecture;

        updateSelectedLectureUI(
            existingLecture
        );

        if (startButton) {
            startButton.disabled =
                false;
        }

        /*
         * If the inline attendance.html script has already
         * selected the lecture and showed "Preparing camera",
         * automatically start the scanner here.
         */
        if (
            !STATE.attendance.running &&
            !STATE.attendance.starting
        ) {

            setTimeout(
                function () {

                    const currentLecture =
                        getLectureFromSelect();

                    if (
                        currentLecture &&
                        !STATE.attendance.running &&
                        !STATE.attendance.starting
                    ) {

                        console.log(
                            "[Attendance] Auto-starting existing selected lecture."
                        );

                        startAttendanceFromLectureSelection(
                            currentLecture
                        );
                    }

                },
                100
            );
        }
    }
}


/* =========================================================
   GLOBAL LECTURE START FUNCTION
========================================================= */

window.startAttendanceFromLectureSelection =
    async function (lecture = null) {

        console.log(
            "[Attendance] startAttendanceFromLectureSelection() called.",
            lecture
        );

        if (!lecture) {

            lecture =
                getLectureFromSelect();
        }

        if (
            !lecture ||
            !lecture.id
        ) {

            setAttendanceMessage(
                "Please select a lecture first.",
                "warning"
            );

            return;
        }

        STATE.lecture =
            lecture;

        updateSelectedLectureUI(
            lecture
        );

        await startAttendanceScanner(
            lecture
        );
    };


/* =========================================================
   START ATTENDANCE SCANNER
========================================================= */

async function startAttendanceScanner(
    lectureOverride = null
) {

    console.log(
        "[Attendance] startAttendanceScanner() called."
    );

    /*
     * Prevent duplicate camera requests.
     */
    if (
        STATE.attendance.starting
    ) {

        console.log(
            "[Attendance] Scanner is already starting."
        );

        return;
    }

    /*
     * Already running.
     */
    if (
        STATE.attendance.running
    ) {

        setAttendanceMessage(
            "Scanner is already running.",
            "info"
        );

        return;
    }

    STATE.attendance.starting =
        true;

    try {

        /* -------------------------------------------------
           GET LECTURE
        ------------------------------------------------- */

        const lecture =
            lectureOverride ||
            STATE.lecture ||
            getLectureFromSelect();

        if (
            !lecture ||
            !lecture.id
        ) {

            throw new Error(
                "Please select a lecture first."
            );
        }

        console.log(
            "[Attendance] Selected lecture:",
            lecture
        );


        /* -------------------------------------------------
           GET CAMERA
        ------------------------------------------------- */

        const video =
            $("attendanceCamera");

        if (!video) {

            throw new Error(
                "Attendance camera element not found."
            );
        }


        /* -------------------------------------------------
           GET CANVAS
        ------------------------------------------------- */

        const canvas =
            $("attendanceCanvas");

        if (!canvas) {

            throw new Error(
                "Attendance canvas element not found."
            );
        }


        /* -------------------------------------------------
           SAVE LECTURE STATE
        ------------------------------------------------- */

        STATE.lecture =
            lecture;

        STATE.attendance.lectureId =
            String(lecture.id);

        STATE.attendance.lectureName =
            lecture.name;

        STATE.attendance.lectureStart =
            lecture.start;

        STATE.attendance.lectureEnd =
            lecture.end;

        STATE.attendance.requiredPercentage =
            safeNumber(
                lecture.required_percentage,
                90
            );


        /* -------------------------------------------------
           RESET ATTENDANCE SESSION STATE
        ------------------------------------------------- */

        STATE.attendance.currentStudentId =
            null;

        STATE.attendance.currentStudentName =
            null;

        STATE.attendance.verifiedSeconds =
            0;

        STATE.attendance.requiredSeconds =
            0;

        STATE.attendance.recognitionErrors =
            0;

        STATE.attendance.lastRecognitionTime =
            null;

        STATE.attendance.verificationStarted =
            false;

        STATE.attendance.recognitionInProgress =
            false;


        updateSelectedLectureUI(
            lecture
        );


        /* -------------------------------------------------
           CAMERA MESSAGE
        ------------------------------------------------- */

        setAttendanceMessage(
            `Opening camera for ${lecture.name}...`,
            "info"
        );


        /* -------------------------------------------------
           OPEN CAMERA
        ------------------------------------------------- */

        console.log(
            "[Attendance] Opening camera..."
        );

        const stream =
            await openCamera(video);

        STATE.attendance.stream =
            stream;


        /* -------------------------------------------------
           CAMERA READY
        ------------------------------------------------- */

        STATE.attendance.running =
            true;

        STATE.attendance.starting =
            false;

        console.log(
            "[Attendance] Camera successfully started."
        );


        /* -------------------------------------------------
           BUTTONS
        ------------------------------------------------- */

        const startButton =
            $("startAttendanceBtn");

        const stopButton =
            $("stopAttendanceBtn");

        if (startButton) {

            startButton.disabled =
                true;

            hideElement(
                startButton
            );
        }

        if (stopButton) {

            showElement(
                stopButton
            );
        }


        /* -------------------------------------------------
           PLACEHOLDER
        ------------------------------------------------- */

        hideElement(
            $("attendancePlaceholder")
        );


        /* -------------------------------------------------
           ACTIVE MESSAGE
        ------------------------------------------------- */

        setAttendanceMessage(
            `${lecture.name} scanner is active. Looking for a registered face...`,
            "info"
        );


        /* -------------------------------------------------
           START TIMERS
        ------------------------------------------------- */

        startRecognitionTimer();

        startVerificationTimer();

        startAttendanceClock();


        /* -------------------------------------------------
           FIRST SCAN
        ------------------------------------------------- */

        setTimeout(
            async function () {

                if (
                    STATE.attendance.running
                ) {

                    await recognizeAttendanceFrame();
                }

            },
            300
        );

    } catch (error) {

        console.error(
            "[Attendance] Start scanner error:",
            error
        );

        STATE.attendance.starting =
            false;

        STATE.attendance.running =
            false;

        clearAttendanceTimers();

        stopCamera(
            $("attendanceCamera")
        );

        STATE.attendance.stream =
            null;

        setAttendanceMessage(
            error.message ||
            "Unable to start scanner.",
            "error"
        );
    }
}


/* =========================================================
   STOP ATTENDANCE SCANNER
========================================================= */

function stopAttendanceScanner() {

    console.log(
        "[Attendance] Stopping scanner."
    );

    clearAttendanceTimers();

    stopCamera(
        $("attendanceCamera")
    );

    STATE.attendance.running =
        false;

    STATE.attendance.starting =
        false;

    STATE.attendance.stream =
        null;

    STATE.attendance.currentStudentId =
        null;

    STATE.attendance.currentStudentName =
        null;

    STATE.attendance.recognitionInProgress =
        false;

    const startButton =
        $("startAttendanceBtn");

    const stopButton =
        $("stopAttendanceBtn");

    if (startButton) {

        showElement(
            startButton
        );

        const lecture =
            getLectureFromSelect();

        startButton.disabled =
            !lecture;
    }

    if (stopButton) {

        hideElement(
            stopButton
        );
    }

    showElement(
        $("attendancePlaceholder")
    );

    setAttendanceMessage(
        "Scanner stopped.",
        "warning"
    );
}


/* =========================================================
   TIMERS
========================================================= */

function startRecognitionTimer() {

    clearInterval(
        STATE.attendance.recognitionTimer
    );

    STATE.attendance.recognitionTimer =
        setInterval(
            function () {

                recognizeAttendanceFrame();

            },
            CONFIG.RECOGNITION_INTERVAL_MS
        );
}


function startVerificationTimer() {

    clearInterval(
        STATE.attendance.verificationTimer
    );

    STATE.attendance.verificationTimer =
        setInterval(
            function () {

                syncVerification();

            },
            CONFIG.VERIFICATION_SYNC_INTERVAL_MS
        );
}


function startAttendanceClock() {

    clearInterval(
        STATE.attendance.clockTimer
    );

    STATE.attendance.clockTimer =
        setInterval(
            updateAttendanceClock,
            1000
        );
}


function clearAttendanceTimers() {

    if (
        STATE.attendance.recognitionTimer
    ) {

        clearInterval(
            STATE.attendance.recognitionTimer
        );

        STATE.attendance.recognitionTimer =
            null;
    }

    if (
        STATE.attendance.verificationTimer
    ) {

        clearInterval(
            STATE.attendance.verificationTimer
        );

        STATE.attendance.verificationTimer =
            null;
    }

    if (
        STATE.attendance.clockTimer
    ) {

        clearInterval(
            STATE.attendance.clockTimer
        );

        STATE.attendance.clockTimer =
            null;
    }
}


/* =========================================================
   RECOGNITION
========================================================= */

async function recognizeAttendanceFrame() {

    if (
        !STATE.attendance.running
    ) {
        return;
    }

    /*
     * Prevent overlapping recognition requests.
     */
    if (
        STATE.attendance.recognitionInProgress
    ) {
        return;
    }

    const video =
        $("attendanceCamera");

    const canvas =
        $("attendanceCanvas");

    if (
        !video ||
        !canvas
    ) {
        return;
    }

    const image =
        captureFrame(
            video,
            canvas
        );

    if (!image) {
        return;
    }

    const lectureId =
        STATE.attendance.lectureId;

    if (!lectureId) {

        setAttendanceMessage(
            "No lecture selected.",
            "warning"
        );

        return;
    }

    STATE.attendance.recognitionInProgress =
        true;

    try {

        console.log(
            "[Recognition] Sending frame for lecture:",
            lectureId
        );

        const response =
            await fetch(
                "/recognize-face",
                {
                    method: "POST",
                    headers: getJSONHeaders(),

                    body: JSON.stringify({

                        image:
                            image,

                        lecture_id:
                            String(lectureId)
                    })
                }
            );

        let result = null;

        try {

            result =
                await response.json();

        } catch (jsonError) {

            throw new Error(
                "Server returned an invalid response."
            );
        }

        if (!response.ok) {

            throw new Error(
                result?.message ||
                "Face recognition request failed."
            );
        }

        STATE.attendance.recognitionErrors =
            0;

        handleRecognitionResult(
            result
        );

    } catch (error) {

        console.error(
            "Recognition error:",
            error
        );

        STATE.attendance.recognitionErrors++;

        if (
            STATE.attendance.recognitionErrors >=
            CONFIG.MAX_RECOGNITION_ERRORS
        ) {

            setAttendanceMessage(
                "Face recognition is temporarily unavailable. Please check the server.",
                "error"
            );
        }

    } finally {

        STATE.attendance.recognitionInProgress =
            false;
    }
}


/* =========================================================
   RECOGNITION RESULT
========================================================= */

function handleRecognitionResult(
    result
) {

    if (!result) {
        return;
    }

    console.log(
        "[Recognition] Result:",
        result
    );

    if (
        result.recognized === true
    ) {

        const studentId =
            result.student_id;

        if (
            studentId === undefined ||
            studentId === null
        ) {

            setAttendanceMessage(
                "Face recognized but student ID was not returned.",
                "warning"
            );

            return;
        }

        STATE.attendance.currentStudentId =
            String(studentId);

        STATE.attendance.lastRecognitionTime =
            Date.now();

        STATE.attendance.currentStudentName =
            result.student_name ||
            result.name ||
            String(studentId);

        updateRecognizedStudentUI(
            result
        );

        setAttendanceMessage(
            `Face recognized: ${STATE.attendance.currentStudentName}`,
            "success"
        );

        ensureAttendanceSession();

        return;
    }

    /*
     * Face not recognized.
     */
    updateRecognizedStudentUI(
        null
    );

    setAttendanceMessage(
        result.message ||
        "Scanning for face match...",
        "info"
    );
}


/* =========================================================
   RECOGNIZED STUDENT UI
========================================================= */

function updateRecognizedStudentUI(
    result
) {

    const name =
        $("recognizedStudentName");

    const id =
        $("recognizedStudentId");

    const confidence =
        $("recognitionConfidence");

    if (!result) {

        setText(
            name,
            "Scanning..."
        );

        setText(
            id,
            "--"
        );

        setText(
            confidence,
            "--"
        );

        return;
    }

    setText(
        name,
        result.student_name ||
        result.name ||
        result.student_id ||
        "Recognized"
    );

    setText(
        id,
        result.student_id ||
        "--"
    );

    setText(
        confidence,
        result.confidence ||
        "--"
    );
}


/* =========================================================
   ATTENDANCE SESSION
========================================================= */

async function ensureAttendanceSession() {

    if (
        !STATE.attendance.running ||
        !STATE.attendance.currentStudentId ||
        !STATE.attendance.lectureId
    ) {
        return;
    }

    if (
        STATE.attendance.verificationStarted
    ) {
        return;
    }

    STATE.attendance.verificationStarted =
        true;

    try {

        const requiredPercentage =
            safeNumber(
                STATE.attendance.requiredPercentage,
                90
            );

        let requiredSeconds =
            60;

        if (
            STATE.attendance.lectureStart &&
            STATE.attendance.lectureEnd
        ) {

            requiredSeconds =
                calculateLectureDurationSeconds(
                    STATE.attendance.lectureStart,
                    STATE.attendance.lectureEnd
                );
        }

        if (
            requiredSeconds <= 0
        ) {

            requiredSeconds =
                60;
        }

        const requiredAttendanceSeconds =
            Math.ceil(
                requiredSeconds *
                requiredPercentage /
                100
            );

        STATE.attendance.requiredSeconds =
            requiredAttendanceSeconds;

        const response =
            await fetch(
                "/start-attendance-session",
                {
                    method: "POST",
                    headers: getJSONHeaders(),

                    body: JSON.stringify({

                        student_id:
                            String(
                                STATE.attendance.currentStudentId
                            ),

                        lecture_id:
                            String(
                                STATE.attendance.lectureId
                            ),

                        required_seconds:
                            requiredAttendanceSeconds
                    })
                }
            );

        const result =
            await response.json();

        if (
            !response.ok ||
            result.success === false
        ) {

            throw new Error(
                result.message ||
                "Unable to start attendance session."
            );
        }

        if (
            result.required_seconds !==
            undefined
        ) {

            STATE.attendance.requiredSeconds =
                safeNumber(
                    result.required_seconds,
                    requiredAttendanceSeconds
                );
        }

        updateAttendanceClock();

    } catch (error) {

        console.error(
            "Attendance session error:",
            error
        );

        STATE.attendance.verificationStarted =
            false;
    }
}


/* =========================================================
   VERIFICATION SYNC
========================================================= */

async function syncVerification() {

    if (
        !STATE.attendance.running ||
        !STATE.attendance.currentStudentId ||
        !STATE.attendance.lectureId
    ) {
        return;
    }

    const lastSeen =
        STATE.attendance.lastRecognitionTime;

    if (!lastSeen) {
        return;
    }

    const elapsed =
        Math.floor(
            (Date.now() - lastSeen) /
            1000
        );

    if (elapsed < 0) {
        return;
    }

    STATE.attendance.verifiedSeconds =
        Math.max(
            STATE.attendance.verifiedSeconds,
            elapsed
        );

    try {

        const response =
            await fetch(
                "/update-attendance-verification",
                {
                    method: "POST",
                    headers: getJSONHeaders(),

                    body: JSON.stringify({

                        student_id:
                            String(
                                STATE.attendance.currentStudentId
                            ),

                        lecture_id:
                            String(
                                STATE.attendance.lectureId
                            ),

                        verified_seconds:
                            STATE.attendance.verifiedSeconds
                    })
                }
            );

        const result =
            await response.json();

        if (
            !response.ok ||
            result.success === false
        ) {

            console.warn(
                "Verification sync failed:",
                result.message
            );

            return;
        }

        if (
            result.verified_seconds !==
            undefined
        ) {

            STATE.attendance.verifiedSeconds =
                Math.max(
                    STATE.attendance.verifiedSeconds,
                    safeNumber(
                        result.verified_seconds
                    )
                );
        }

        updateAttendanceClock();

    } catch (error) {

        console.error(
            "Verification sync error:",
            error
        );
    }
}


/* =========================================================
   ATTENDANCE CLOCK / PROGRESS
========================================================= */

function updateAttendanceClock() {

    const verified =
        STATE.attendance.verifiedSeconds;

    const required =
        STATE.attendance.requiredSeconds;

    setText(
        $("verifiedTime"),
        formatSeconds(verified)
    );

    setText(
        $("requiredTime"),
        formatSeconds(required)
    );

    let percentage = 0;

    if (required > 0) {

        percentage =
            Math.min(
                100,
                Math.round(
                    verified /
                    required *
                    100
                )
            );
    }

    setText(
        $("verificationPercentage"),
        `${percentage}%`
    );

    const progress =
        $("verificationProgress");

    if (progress) {

        progress.style.width =
            `${percentage}%`;
    }

    const status =
        $("attendanceStatus");

    if (!status) {
        return;
    }

    if (
        percentage >= 100
    ) {

        status.textContent =
            "Attendance requirement completed";

        status.classList.remove(
            "warning",
            "info"
        );

        status.classList.add(
            "success"
        );

    } else if (
        percentage > 0
    ) {

        status.textContent =
            "Attendance verification in progress";

        status.classList.remove(
            "success",
            "warning"
        );

        status.classList.add(
            "info"
        );

    } else {

        status.textContent =
            "Waiting for face verification";
    }
}


/* =========================================================
   FINALIZE ATTENDANCE
========================================================= */

async function finalizeAttendance() {

    if (
        !STATE.attendance.currentStudentId ||
        !STATE.attendance.lectureId
    ) {
        return;
    }

    try {

        const response =
            await fetch(
                "/finalize-attendance",
                {
                    method: "POST",
                    headers: getJSONHeaders(),

                    body: JSON.stringify({

                        student_id:
                            String(
                                STATE.attendance.currentStudentId
                            ),

                        lecture_id:
                            String(
                                STATE.attendance.lectureId
                            )
                    })
                }
            );

        const result =
            await response.json();

        if (
            !response.ok ||
            result.success === false
        ) {

            throw new Error(
                result.message ||
                "Unable to finalize attendance."
            );
        }

        setAttendanceMessage(
            result.message ||
            "Attendance finalized successfully.",
            "success"
        );

    } catch (error) {

        console.error(
            "Finalize attendance error:",
            error
        );

        setAttendanceMessage(
            error.message ||
            "Attendance finalization failed.",
            "error"
        );
    }
}


/* =========================================================
   LECTURE DURATION
========================================================= */

function calculateLectureDurationSeconds(
    start,
    end
) {

    if (
        !start ||
        !end
    ) {
        return 0;
    }

    try {

        const startParts =
            String(start)
                .split(":")
                .map(Number);

        const endParts =
            String(end)
                .split(":")
                .map(Number);

        if (
            startParts.length < 2 ||
            endParts.length < 2
        ) {
            return 0;
        }

        const startMinutes =
            startParts[0] * 60 +
            startParts[1];

        const endMinutes =
            endParts[0] * 60 +
            endParts[1];

        let duration =
            endMinutes -
            startMinutes;

        if (
            duration < 0
        ) {

            duration +=
                24 * 60;
        }

        return duration * 60;

    } catch (error) {

        console.warn(
            "Lecture duration error:",
            error
        );

        return 0;
    }
}


/* =========================================================
   HISTORY SEARCH
========================================================= */

function initializeHistorySearch() {

    const searchInput =
        $("historySearch");

    if (!searchInput) {
        return;
    }

    searchInput.addEventListener(
        "input",
        function () {

            const query =
                this.value
                    .trim()
                    .toLowerCase();

            const rows =
                document.querySelectorAll(
                    "#historyTable tbody tr"
                );

            rows.forEach(
                row => {

                    const text =
                        row.textContent
                            .toLowerCase();

                    row.style.display =
                        !query ||
                        text.includes(query)
                            ? ""
                            : "none";
                }
            );
        }
    );
}


/* =========================================================
   GLOBAL PAGE INITIALIZATION
========================================================= */

document.addEventListener(
    "DOMContentLoaded",
    function () {

        console.log(
            "========================================"
        );

        console.log(
            "Smart Attendance System JS loaded."
        );

        console.log(
            "========================================"
        );

        initializeRegistration();

        initializeAttendance();

        initializeHistorySearch();

        console.log(
            "[Debug] Attendance camera:",
            !!$("attendanceCamera")
        );

        console.log(
            "[Debug] Lecture select:",
            !!$("lectureSelect")
        );

        console.log(
            "[Debug] Start scanner button:",
            !!$("startAttendanceBtn")
        );

        console.log(
            "[Debug] Selected lecture:",
            getLectureFromSelect()
        );
    }
);


/* =========================================================
   BEFORE PAGE UNLOAD
========================================================= */

window.addEventListener(
    "beforeunload",
    function () {

        clearAttendanceTimers();

        stopCamera(
            $("attendanceCamera")
        );

        stopCamera(
            $("registrationCamera")
        );
    }
);


/* =========================================================
   GLOBAL FUNCTIONS
========================================================= */

window.startAttendanceScanner =
    startAttendanceScanner;

window.stopAttendanceScanner =
    stopAttendanceScanner;

window.recognizeAttendanceFrame =
    recognizeAttendanceFrame;

window.finalizeAttendance =
    finalizeAttendance;

window.captureRegistrationSample =
    captureRegistrationSample;

window.startRegistrationCamera =
    startRegistrationCamera;

window.stopRegistrationCamera =
    stopRegistrationCamera;

window.captureFrame =
    captureFrame;

window.openCamera =
    openCamera;


console.log(
    "Smart Attendance System JavaScript ready."
);