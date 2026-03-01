import fs from 'fs/promises';
import path from 'path';


export interface FileSystemResult {
	ok: boolean;
	content?: string | Uint8Array;
	error?: string;
}

/**
 * List contents of a directory
 */
export async function listDirectory(dirPath: string, workspace: string): Promise<FileSystemResult> {
	try {
		const fullPath = workspace ? path.join(workspace, dirPath) : dirPath;
		const entries = await fs.readdir(fullPath, { withFileTypes: true });
		const content = entries.map(entry => entry.name).join('\n');

		return { ok: true, content };
	} catch (err: any) {
		return { ok: false, error: err.message };
	}
}

/**
 * Read file as raw bytes
 */
export async function readFileBytes(filePath: string, workspace: string): Promise<FileSystemResult> {
	try {

		const fullPath = workspace ? path.join(workspace, filePath) : filePath;
		const content = await fs.readFile(fullPath);
		
		return { ok: true, content };
	} catch (err: any) {
		return { ok: false, error: err.message };
	}
}

/**
 * Read file as UTF-8 text
 */
export async function readFileText(filePath: string, workspace: string): Promise<FileSystemResult> {
	try {
		const fullPath = workspace ? path.join(workspace, filePath) : filePath;
		const content = await fs.readFile(fullPath, 'utf8');
		
		return { ok: true, content };
	} catch (err: any) {
		return { ok: false, error: err.message };
	}
}

/**
 * Write content to file
 */
export async function writeFile(filePath: string, content: string, workspace: string): Promise<FileSystemResult> {
	try {
		const fullPath = workspace ? path.join(workspace, filePath) : filePath;
		const parentDir = path.dirname(fullPath);
		
		// Create parent directory if it doesn't exist
		await fs.mkdir(parentDir, { recursive: true });
		await fs.writeFile(fullPath, content, 'utf8');
		
		return { ok: true };
	} catch (err: any) {
		return { ok: false, error: err.message };
	}
}