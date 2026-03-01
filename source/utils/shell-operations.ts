import { spawn } from 'child_process';

interface ShellCommandResult {
    return_code: number;
    stdout: string;
    stderr: string;
}

export async function runCommand(cmd_parts: string[], cwd: string, timeout: number): Promise<ShellCommandResult> {
    return new Promise((resolve) => {
            if (cmd_parts.length === 0) {
                resolve({
                    return_code: -1,
                    stdout: '',
                    stderr: 'Command array is empty.'
                });
                return;
            }
            
            const [command, ...args] = cmd_parts;
            
            // 1. Create the subprocess
            const process = spawn(command as string, args, {
                cwd: cwd,
                shell: false // Use false for security if using cmd_parts array
            });

            let stdout = '';
            let stderr = '';

            // 2. Set up a timeout timer
            const timer = setTimeout(() => {
                process.kill();
                resolve({
                    return_code: -1,
                    stdout: '',
                    stderr: `Command timed out after ${timeout / 1000} seconds.`
                });
            }, timeout);

            // 3. Capture output
            process.stdout.on('data', (data) => {
                stdout += data.toString();
            });

            process.stderr.on('data', (data) => {
                stderr += data.toString();
            });

            // 4. Handle completion
            process.on('close', (code) => {
                clearTimeout(timer);
                resolve({
                    return_code: code ?? -1,
                    stdout: stdout.trim(),
                    stderr: stderr.trim()
                });
            });

            // 5. Handle immediate execution errors (e.g., command not found)
            process.on('error', (err) => {
                clearTimeout(timer);
                resolve({
                    return_code: -1,
                    stdout: '',
                    stderr: err.message
                });
            });
        });
}