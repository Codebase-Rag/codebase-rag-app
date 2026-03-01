export async function sendMessage(
    question: string,  
    socketId: string,
    mode: string, 
    sessionId?: string, 
): Promise<{session_id: string, response: string, edit: boolean}> {
    const res = await fetch(`${process.env['BACKEND_URI']}/remote/repo/query`, {
        method: "POST", 
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(
            {
                question: question, 
                socket_id: socketId,
                mode: mode,  
                session_id: sessionId,  
            }
        )
    });
    return res.json();
}

export async function rejectChange(
    socketId: string,
    sessionId: string, 
): Promise<{response: string}> {
    const res = await fetch(`${process.env['BACKEND_URI']}/remote/repo/reject/sessions/${sessionId}?socket_id=${encodeURIComponent(socketId)}`, {
        method: "DELETE", 
    });
    return res.json();
}