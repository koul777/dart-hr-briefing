import {Composition} from 'remotion';
import {DartPromo, TOTAL_FRAMES} from './DartPromo';

export const Root = () => (
  <Composition
    id="DARTPromo"
    component={DartPromo}
    durationInFrames={TOTAL_FRAMES}
    fps={30}
    width={1920}
    height={1080}
  />
);
