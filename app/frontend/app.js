const API =
    "http://127.0.0.1:8000";


const output =
    document.getElementById(
        "output"
    );

function renderTypedOutput(data) {
    const descriptor = data && data.output;
    output.replaceChildren();
    if (!descriptor || descriptor.type === "json") {
        output.textContent = data && data.message
            ? data.message
            : "Structured response received.";
        return;
    }
    if (descriptor.type === "text") {
        output.textContent = descriptor.content || "";
        return;
    }
    const media = document.createElement(descriptor.type);
    media.src = descriptor.url;
    if (descriptor.type !== "image") media.controls = true;
    media.alt = descriptor.type === "image" ? "Lumira generated output" : "";
    output.appendChild(media);
}


async function loadProjects() {

    try {

        const response =
            await fetch(
                API + "/projects"
            );

        const data =
            await response.json();

        let html = "";


        for (

            const project

            of

            data.projects

        ) {

            html += `

            <div class="project-card">

                <h3>
                    ${project.project}
                </h3>

                <p>
                    Versions:
                    ${project.versions}
                </p>

                <button
                    onclick="
                        openProject(
                            '${project.project}'
                        )
                    "
                >
                    Open
                </button>

            </div>

            `;
        }


        document
            .getElementById(
                "projects"
            )
            .innerHTML =
            html;

    }

    catch (error) {

        output.textContent =
            error.toString();
    }
}


async function openProject(
    project
) {

    try {

        const response =
            await fetch(

                API +
                "/projects/" +
                project

            );

        const data =
            await response.json();

        let html = `

            <h2>
                ${project}
            </h2>

        `;


        for (

            const version

            of

            data.versions

        ) {

            html += `

                <button
                    onclick="
                        openVersion(
                            '${project}',
                            '${version}'
                        )
                    "
                >

                    ${version}

                </button>

            `;
        }


        output.innerHTML =
            html;

    }

    catch (error) {

        output.textContent =
            error.toString();
    }
}


async function openVersion(
    project,
    version
) {

    try {

        const response =
            await fetch(

                API +
                "/projects/" +
                project +
                "/" +
                version +
                "/files"

            );

        const data =
            await response.json();

        let html = `

            <h2>
                ${project}
            </h2>

            <h3>
                ${version}
            </h3>

        `;


        for (

            const file

            of

            data.files

        ) {

            html += `

                <button
                    onclick="
                        openFile(
                            '${project}',
                            '${version}',
                            '${file}'
                        )
                    "
                >

                    ${file}

                </button>

            `;
        }


        output.innerHTML =
            html;

    }

    catch (error) {

        output.textContent =
            error.toString();
    }
}


async function openFile(
    project,
    version,
    file
) {

    try {

        const response =
            await fetch(

                API +
                "/projects/" +
                project +
                "/" +
                version +
                "/" +
                file

            );

        const data =
            await response.json();

        output.innerHTML =

            `

            <h2>

                ${project}

            </h2>

            <h3>

                ${version}

            </h3>

            <h4>

                ${file}

            </h4>

            <pre>

${data.content}

            </pre>

            `;

    }

    catch (error) {

        output.textContent =
            error.toString();
    }
}


document
.getElementById(
    "runBtn"
)
.onclick = async () => {

    const prompt =

        document
        .getElementById(
            "prompt"
        )
        .value;


    try {

        const response =
            await fetch(

                API + "/run",

                {
                    method: "POST",

                    headers: {

                        "Content-Type":
                        "application/json"
                    },

                    body: JSON.stringify({

                        input: prompt
                    })
                }
            );


        const data =
            await response.json();

        renderTypedOutput(data);

        loadProjects();

    }

    catch (error) {

        output.textContent =
            error.toString();
    }
};


let recognition;


if (
    "webkitSpeechRecognition"
    in
    window
) {

    recognition =
        new webkitSpeechRecognition();

    recognition.continuous =
        false;

    recognition.lang =
        "en-US";


    recognition.onresult =
    (event) => {

        document
        .getElementById(
            "prompt"
        )
        .value =

        event
        .results[0][0]
        .transcript;
    };


    document
    .getElementById(
        "voiceBtn"
    )
    .onclick = () => {

        recognition.start();
    };

}
else {

    document
    .getElementById(
        "voiceBtn"
    )
    .disabled = true;
}


loadProjects();