import React, {useState, useEffect} from 'react';
import {Box, Text} from 'ink';

type Props = {
	onComplete: () => void;
};

const treeFrames = [
	// Frame 1: Ground only
	String.raw`
                     
                     
                     
                     
                     
                     
                     
                     
                     
                     |   =|
                     |    |
--------------------/ ,  . \--------._
`,
	// Frame 2: Trunk grows
	String.raw`
                     
                     
                     
                     
                     
                     
                     
                     |    |//
                     |_    /
                     |-   |
                     |   =|
                     |    |
--------------------/ ,  . \--------._
`,
	// Frame 3: Lower branches
	String.raw`
                     
                     
                     
                     
           '7-,--.   ||  / / ,
           /'       . / / |/_.'
                     |    |//
                     |_    /
                     |-   |
                     |   =|
                     |    |
--------------------/ ,  . \--------._
`,
	// Frame 4: More branches
	String.raw`
                     
                     
               \\     y |  //
         _ _.___\\,  / -. ||
           '7-,--.'._||  / / ,
           /'     '-. './ / |/_.'
                     |    |//
                     |_    /
                     |-   |
                     |   =|
                     |    |
--------------------/ ,  . \--------._
`,
	// Frame 5: Full tree
	String.raw`
              v .   ._, |_  .,
           '-._\/  .  \ /    |/_
               \\  _\, y | \//
         _\_.___\\, \\/ -.\||
           '7-,--.'. ||  / / ,
           /'     '-. './ / |/_.'
                     |    |//
                     |_    /
                     |-   |
                     |   =|
                     |    |
--------------------/ ,  . \--------._
`,
];

export default function TreeAnimation({onComplete}: Props) {
	const [frameIndex, setFrameIndex] = useState(0);

	useEffect(() => {
		if (frameIndex < treeFrames.length - 1) {
			const timer = setTimeout(() => {
				setFrameIndex((prev) => prev + 1);
			}, 200);
			return () => clearTimeout(timer);
		} else {
			const timer = setTimeout(() => {
				onComplete();
			}, 800);
			return () => clearTimeout(timer);
		}
	}, [frameIndex, onComplete]);

	return (
		<Box flexDirection="column" alignItems="center" justifyContent="center" padding={2}>
			<Text color="green">{treeFrames[frameIndex]}</Text>
			<Text color="cyan" bold>
				Codebase RAG Agent
			</Text>
		</Box>
	);
}
