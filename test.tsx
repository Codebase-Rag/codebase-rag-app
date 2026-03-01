import React from 'react';
import test from 'ava';
import {render} from 'ink-testing-library';
import App from './source/app.js';

test('renders header', (t) => {
	const {lastFrame} = render(<App />);
	const frame = lastFrame() ?? '';
	t.true(frame.includes('Gemini Terminal Agent'));
});
