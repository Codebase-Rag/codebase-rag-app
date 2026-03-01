import fs from 'fs/promises';
import path from 'path';

/**
 * Validates if a given path is a valid directory
 */
export async function isValidDirectory(dirPath: string): Promise<boolean> {
	try {
		const stats = await fs.stat(dirPath);
		return stats.isDirectory();
	} catch {
		return false;
	}
}

/**
 * Resolves a path relative to the current working directory
 */
export function resolvePath(inputPath: string): string {
	return path.resolve(inputPath);
}

/**
 * Gets basic info about a workspace directory
 */
export async function getWorkspaceInfo(dirPath: string): Promise<{
	exists: boolean;
	isDirectory: boolean;
	absolutePath: string;
	name: string;
}> {
	const absolutePath = resolvePath(dirPath);
	const name = path.basename(absolutePath);

	try {
		const stats = await fs.stat(absolutePath);
		return {
			exists: true,
			isDirectory: stats.isDirectory(),
			absolutePath,
			name
		};
	} catch {
		return {
			exists: false,
			isDirectory: false,
			absolutePath,
			name
		};
	}
}