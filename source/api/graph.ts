import { processFiles } from "../utils/file-operations.js";

export async function sendProjectFiles(
    socketId: string,
    workspace: string, 
): Promise<{status: string, message: string, files_processed: number}> {
    const res = await fetch(`${process.env['BACKEND_URI']}/remote/repo/ingest`, {
        method: "POST", 
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(
            {
                project_name: workspace, 
                socket_id: socketId, 
                files: await processFiles(workspace), 
            }
        )
    });
    return res.json();
}
