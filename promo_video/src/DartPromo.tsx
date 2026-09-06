import type {CSSProperties, ReactNode} from 'react';
import {
  AbsoluteFill,
  Audio,
  Easing,
  Img,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
} from 'remotion';

export const COLORS = {
  ink: '#17312f',
  muted: '#60726c',
  faint: '#8a9893',
  line: '#dce6df',
  paper: '#f4f6f2',
  card: '#ffffff',
  mint: '#e6f4ec',
  teal: '#0b7668',
  tealDark: '#08665c',
  coral: '#a84736',
  gold: '#9a6808',
  navy: '#1c2d52',
};

const FONT = '"Noto Sans KR", "Malgun Gothic", "Segoe UI", sans-serif';
const MONO = 'Consolas, "Noto Sans KR", monospace';
const ease = Easing.bezier(0.32, 0, 0.16, 1);
const springEase = Easing.bezier(0.2, 0.9, 0.25, 1.12);

export const SHOTS = {
  opening: {from: 0, duration: 220},
  title1: {from: 220, duration: 55},
  compare: {from: 275, duration: 190},
  detail: {from: 465, duration: 100},
  title2: {from: 565, duration: 55},
  strategy: {from: 620, duration: 105},
  title3: {from: 725, duration: 50},
  ai: {from: 775, duration: 110},
  title4: {from: 885, duration: 55},
  outro: {from: 940, duration: 145},
} as const;

export const TOTAL_FRAMES = 1085;

const clamp = {
  extrapolateLeft: 'clamp' as const,
  extrapolateRight: 'clamp' as const,
};

const fadeWindow = (frame: number, duration: number, inFrames = 10, outFrames = 10) =>
  interpolate(frame, [0, inFrames, duration - outFrames, duration], [0, 1, 1, 0], clamp);

const PaperTexture = ({dark = false}: {dark?: boolean}) => (
  <AbsoluteFill
    style={{
      pointerEvents: 'none',
      opacity: dark ? 0.16 : 0.36,
      backgroundImage: dark
        ? 'radial-gradient(circle at 20% 20%, rgba(101,206,179,.15) 0 1px, transparent 1.5px)'
        : 'radial-gradient(circle at 20% 20%, rgba(23,49,47,.13) 0 1px, transparent 1.5px)',
      backgroundSize: '22px 22px',
      mixBlendMode: dark ? 'screen' : 'multiply',
    }}
  />
);

const BrandMark = ({size = 74}: {size?: number}) => (
  <div
    style={{
      width: size,
      height: size,
      borderRadius: size * 0.24,
      transform: 'rotate(-7deg)',
      display: 'grid',
      placeItems: 'center',
      background: COLORS.teal,
      color: 'white',
      fontFamily: FONT,
      fontSize: size * 0.55,
      fontWeight: 900,
      boxShadow: '0 18px 40px rgba(11,118,104,.22)',
    }}
  >
    D
  </div>
);

type BrowserFrameProps = {
  src: string;
  width?: number;
  height?: number;
  style?: CSSProperties;
  objectPosition?: string;
  imageStyle?: CSSProperties;
  label?: string;
  children?: ReactNode;
};

export const BrowserFrame = ({
  src,
  width = 1640,
  height = 900,
  style,
  objectPosition = 'center center',
  imageStyle,
  label = 'DART HR BRIEFING / LIVE PRODUCT',
  children,
}: BrowserFrameProps) => (
  <div
    style={{
      position: 'absolute',
      width,
      height,
      overflow: 'hidden',
      borderRadius: 25,
      border: `1px solid ${COLORS.line}`,
      background: COLORS.card,
      boxShadow: '0 34px 90px rgba(23,49,47,.18), 0 6px 20px rgba(23,49,47,.1)',
      ...style,
    }}
  >
    <div
      style={{
        height: 46,
        padding: '0 22px',
        display: 'flex',
        alignItems: 'center',
        gap: 9,
        borderBottom: `1px solid ${COLORS.line}`,
        background: 'rgba(255,255,255,.96)',
      }}
    >
      {[COLORS.coral, COLORS.gold, COLORS.teal].map((color) => (
        <span key={color} style={{width: 10, height: 10, borderRadius: '50%', background: color, opacity: 0.78}} />
      ))}
      <span style={{marginLeft: 11, color: COLORS.faint, font: `700 13px ${MONO}`, letterSpacing: '.08em'}}>{label}</span>
    </div>
    <div style={{position: 'relative', height: height - 46, overflow: 'hidden', background: COLORS.paper}}>
      <Img
        src={staticFile(`screens/${src}`)}
        style={{width: '100%', height: '100%', objectFit: 'cover', objectPosition, display: 'block', ...imageStyle}}
      />
      {children}
    </div>
  </div>
);

export const Caption = ({text, duration, accent = COLORS.teal}: {text: string; duration: number; accent?: string}) => {
  const frame = useCurrentFrame();
  const opacity = fadeWindow(frame, duration, 8, 8);
  return (
    <div
      style={{
        position: 'absolute',
        left: 0,
        right: 0,
        bottom: 54,
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        gap: 14,
        opacity,
        transform: `translateY(${(1 - opacity) * 8}px)`,
        pointerEvents: 'none',
      }}
    >
      <span style={{width: 8, height: 8, borderRadius: 2, background: accent}} />
      <span
        style={{
          padding: '12px 18px',
          borderRadius: 8,
          background: 'rgba(244,246,242,.92)',
          boxShadow: '0 8px 28px rgba(23,49,47,.12)',
          color: COLORS.ink,
          font: `900 56px ${FONT}`,
          letterSpacing: '-.025em',
        }}
      >
        {text}
      </span>
    </div>
  );
};

export const FlashCut = ({duration = 10}: {duration?: number}) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, duration * 0.42, duration], [0, 0.84, 0], clamp);
  return (
    <AbsoluteFill
      style={{
        pointerEvents: 'none',
        opacity,
        background: 'radial-gradient(ellipse at 50% 45%, rgba(239,255,249,.98), rgba(230,244,236,.7) 55%, transparent 82%)',
      }}
    />
  );
};

export const TitleCard = ({text, duration, sub}: {text: string; duration: number; sub?: string}) => {
  const frame = useCurrentFrame();
  const words = text.split(/\s+/).filter(Boolean);
  const underline = interpolate(frame, [14, 34], [0, 1], {...clamp, easing: ease});
  const opacity = fadeWindow(frame, duration, 3, 5);
  return (
    <AbsoluteFill style={{background: COLORS.paper, justifyContent: 'center', alignItems: 'center', opacity}}>
      <PaperTexture />
      <div style={{width: 1500, textAlign: 'center'}}>
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            justifyContent: 'center',
            columnGap: '0.25em',
            rowGap: '0.05em',
            color: COLORS.ink,
            fontFamily: FONT,
            fontSize: words.length > 8 ? 87 : 102,
            fontWeight: 900,
            lineHeight: 1.22,
            letterSpacing: '-.06em',
          }}
        >
          {words.map((raw, index) => {
            const accent = raw.startsWith('*') && raw.endsWith('*');
            const word = (accent ? raw.slice(1, -1) : raw).replaceAll('_', ' ');
            const t = interpolate(frame, [2 + index * 1.2, 8 + index * 1.2], [0, 1], {...clamp, easing: springEase});
            return (
              <span
                key={`${word}-${index}`}
                style={{
                  display: 'inline-block',
                  opacity: t,
                  color: accent ? COLORS.teal : undefined,
                  transform: `translateY(${(1 - t) * 22}px) scale(${1.1 - t * 0.1})`,
                  filter: `blur(${(1 - t) * 7}px)`,
                }}
              >
                {word}
              </span>
            );
          })}
        </div>
        <div style={{width: 250, height: 7, margin: '38px auto 0', borderRadius: 8, background: COLORS.teal, transform: `scaleX(${underline})`}} />
        {sub ? (
          <div style={{marginTop: 28, color: COLORS.muted, font: `800 32px ${MONO}`, letterSpacing: '.06em'}}>{sub}</div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};

export const OpeningScene = () => {
  const frame = useCurrentFrame();
  const duration = SHOTS.opening.duration;
  const brandIn = interpolate(frame, [0, 18], [0, 1], {...clamp, easing: springEase});
  const brandOut = interpolate(frame, [68, 84], [1, 0], {...clamp, easing: ease});
  const screenIn = interpolate(frame, [72, 99], [0, 1], {...clamp, easing: springEase});
  const push = interpolate(frame, [99, 220], [0, 1], {...clamp, easing: ease});
  const scan = interpolate(frame, [118, 190], [-260, 2060], clamp);
  const sceneOpacity = interpolate(frame, [duration - 6, duration], [1, 0], clamp);
  return (
    <AbsoluteFill style={{background: COLORS.paper, overflow: 'hidden', opacity: sceneOpacity}}>
      <PaperTexture />
      <AbsoluteFill
        style={{
          justifyContent: 'center',
          alignItems: 'center',
          opacity: brandIn * brandOut,
          transform: `translateY(${(1 - brandIn) * 24}px) scale(${0.96 + brandIn * 0.04})`,
        }}
      >
        <BrandMark size={98} />
        <div style={{marginTop: 36, color: COLORS.ink, font: `900 118px ${FONT}`, letterSpacing: '-.065em'}}>DART HR Briefing</div>
        <div style={{width: 260, height: 7, marginTop: 28, borderRadius: 10, background: COLORS.teal}} />
        <div style={{marginTop: 30, color: COLORS.muted, font: `800 34px ${MONO}`, letterSpacing: '.08em'}}>OPENDART → PEOPLE ANALYTICS → EVIDENCE</div>
      </AbsoluteFill>
      {frame >= 72 ? (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            opacity: screenIn,
            transform: `perspective(1800px) translateY(${(1 - screenIn) * 90 - push * 18}px) scale(${0.9 + screenIn * 0.08 + push * 0.04}) rotateX(${(1 - screenIn) * 7 - push * 1.2}deg)`,
            transformOrigin: '50% 45%',
          }}
        >
          <BrowserFrame src="app-home.png" width={1500} height={840} style={{left: 210, top: 120}} objectPosition="center top">
            <div
              style={{
                position: 'absolute',
                left: interpolate(scan, [-260, 2060], [-240, 1740], clamp),
                top: 0,
                width: 220,
                height: '100%',
                transform: 'skewX(-10deg)',
                background: 'linear-gradient(90deg, transparent, rgba(101,206,179,.22), transparent)',
                mixBlendMode: 'screen',
              }}
            />
          </BrowserFrame>
        </div>
      ) : null}
      {frame >= 114 ? (
        <div
          style={{
            position: 'absolute',
            right: 118,
            top: 112,
            padding: '14px 20px',
            borderRadius: 10,
            background: COLORS.ink,
            color: '#fff',
            opacity: interpolate(frame, [114, 126], [0, 1], clamp),
            font: `900 32px ${FONT}`,
            boxShadow: '0 14px 38px rgba(23,49,47,.28)',
          }}
        >
          실제 서비스 화면
        </div>
      ) : null}
    </AbsoluteFill>
  );
};

export const CompareScene = () => {
  const frame = useCurrentFrame();
  const duration = SHOTS.compare.duration;
  const panelIn = interpolate(frame, [0, 24], [0, 1], {...clamp, easing: springEase});
  const companyIn = interpolate(frame, [28, 48], [0, 1], {...clamp, easing: springEase});
  const camera = interpolate(frame, [45, duration], [0, 1], {...clamp, easing: ease});
  const pulse = 1 + Math.sin((frame - 52) / 8) * 0.008;
  return (
    <AbsoluteFill style={{background: COLORS.paper, overflow: 'hidden', opacity: fadeWindow(frame, duration, 7, 7)}}>
      <PaperTexture />
      <div
        style={{
          position: 'absolute',
          inset: 0,
          transform: `perspective(1700px) translate(${camera * -28}px, ${camera * -18}px) scale(${0.94 + camera * 0.08}) rotateY(${3 - camera * 3}deg)`,
          opacity: panelIn,
        }}
      >
        <BrowserFrame src="tab-overview.png" width={1640} height={914} style={{left: 200, top: 80}} objectPosition="center top" />
      </div>
      <div
        style={{
          position: 'absolute',
          left: 70,
          top: 160,
          width: 356,
          height: 430,
          overflow: 'hidden',
          borderRadius: 22,
          border: `2px solid ${COLORS.teal}`,
          background: COLORS.card,
          boxShadow: '0 32px 70px rgba(23,49,47,.24)',
          opacity: companyIn,
          transform: `translateX(${(1 - companyIn) * -120}px) rotate(-2deg) scale(${pulse})`,
        }}
      >
        <Img src={staticFile('screens/companies-selected.png')} style={{width: '100%', height: '100%', objectFit: 'cover', objectPosition: 'top'}} />
      </div>
      {['동일 기준년', '동일 보고서', '최대 8개 기업'].map((label, index) => {
        const t = interpolate(frame, [62 + index * 9, 74 + index * 9], [0, 1], {...clamp, easing: springEase});
        return (
          <div
            key={label}
            style={{
              position: 'absolute',
              right: 86,
              top: 108 + index * 62,
              padding: '11px 17px',
              borderRadius: 999,
              border: `1px solid ${COLORS.line}`,
              background: 'rgba(255,255,255,.94)',
              color: index === 2 ? COLORS.teal : COLORS.ink,
              font: `800 30px ${FONT}`,
              opacity: t,
              transform: `translateX(${(1 - t) * 30}px)`,
              boxShadow: '0 10px 24px rgba(23,49,47,.1)',
            }}
          >
            {label}
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

export const DetailScene = () => {
  const frame = useCurrentFrame();
  const duration = SHOTS.detail.duration;
  const t = interpolate(frame, [0, duration], [0, 1], {...clamp, easing: ease});
  const focus = interpolate(frame, [18, 32, 76, 92], [0, 1, 1, 0], clamp);
  return (
    <AbsoluteFill style={{background: COLORS.paper, overflow: 'hidden', opacity: fadeWindow(frame, duration, 5, 7)}}>
      <PaperTexture />
      <div style={{position: 'absolute', inset: 0, transform: `translateY(${-8 - t * 22}px) scale(${1.015 + t * 0.075})`}}>
        <BrowserFrame src="tab-compare.png" width={1760} height={974} style={{left: 80, top: 54}} objectPosition="center top" />
      </div>
      <div
        style={{
          position: 'absolute',
          left: 446,
          right: 68,
          top: 410,
          height: 500,
          border: `4px solid ${COLORS.teal}`,
          borderRadius: 18,
          opacity: focus,
          boxShadow: '0 0 0 999px rgba(23,49,47,.11), 0 0 45px rgba(11,118,104,.22)',
        }}
      />
      <div
        style={{
          position: 'absolute',
          right: 96,
          top: 86,
          padding: '12px 18px',
          borderRadius: 10,
          background: COLORS.teal,
          color: 'white',
          opacity: interpolate(frame, [20, 33], [0, 1], clamp),
          font: `800 30px ${MONO}`,
          letterSpacing: '.06em',
        }}
      >
        SIDE BY SIDE · 2024 사업보고서
      </div>
    </AbsoluteFill>
  );
};

export const StrategyScene = () => {
  const frame = useCurrentFrame();
  const duration = SHOTS.strategy.duration;
  const screenIn = interpolate(frame, [0, 12], [0, 1], clamp);
  const evidenceWipe = interpolate(frame, [48, 63], [0, 1], {...clamp, easing: ease});
  const badge = interpolate(frame, [67, 79], [0, 1], {...clamp, easing: springEase});
  return (
    <AbsoluteFill style={{background: COLORS.paper, overflow: 'hidden', opacity: fadeWindow(frame, duration, 5, 6)}}>
      <PaperTexture />
      <div style={{position: 'absolute', inset: 0, opacity: screenIn, transform: `scale(${1.01 + frame * 0.00035})`}}>
        <BrowserFrame src="tab-strategy.png" width={1740} height={966} style={{left: 90, top: 56}} objectPosition="center 20%" />
      </div>
      <div style={{position: 'absolute', inset: 0, clipPath: `inset(0 ${(1 - evidenceWipe) * 100}% 0 0)`, transform: `scale(${1.01 + frame * 0.00035})`}}>
        <BrowserFrame src="strategy-evidence.png" width={1740} height={966} style={{left: 90, top: 56}} objectPosition="center center" label="EVIDENCE / ORCHESTRATION" />
      </div>
      <div
        style={{
          position: 'absolute',
          right: 114,
          bottom: 92,
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          padding: '16px 22px',
          borderRadius: 12,
          background: COLORS.ink,
          color: '#fff',
          opacity: badge,
          transform: `translateY(${(1 - badge) * 30}px)`,
          boxShadow: '0 20px 46px rgba(23,49,47,.28)',
          font: `900 34px ${FONT}`,
        }}
      >
        <span style={{width: 10, height: 10, borderRadius: '50%', background: '#65ceb3'}} />
        근거 81개 · 원문 연결 2/2
      </div>
    </AbsoluteFill>
  );
};

const Gate = ({label, index, frame}: {label: string; index: number; frame: number}) => {
  const t = interpolate(frame, [30 + index * 9, 42 + index * 9], [0, 1], {...clamp, easing: springEase});
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '22px 24px',
        borderRadius: 16,
        border: '1px solid rgba(101,206,179,.28)',
        background: 'rgba(255,255,255,.07)',
        opacity: t,
        transform: `translateY(${(1 - t) * 22}px)`,
      }}
    >
      <span style={{color: '#e5f0e8', font: `800 34px ${FONT}`}}>{label}</span>
      <span style={{width: 34, height: 34, borderRadius: '50%', display: 'grid', placeItems: 'center', background: '#65ceb3', color: COLORS.ink, font: `900 21px ${FONT}`}}>✓</span>
    </div>
  );
};

export const AiScene = () => {
  const frame = useCurrentFrame();
  const duration = SHOTS.ai.duration;
  const panel = interpolate(frame, [4, 23], [0, 1], {...clamp, easing: springEase});
  const scan = interpolate(frame, [20, 88], [0, 1], clamp);
  const guards = ['개인정보', '근거 연결', '인과 표현', '개인 판단'];
  return (
    <AbsoluteFill style={{background: COLORS.ink, overflow: 'hidden', opacity: fadeWindow(frame, duration, 5, 7)}}>
      <Img
        src={staticFile('screens/strategy-evidence.png')}
        style={{position: 'absolute', inset: -80, width: 2080, height: 1240, objectFit: 'cover', filter: 'blur(9px) saturate(.7)', opacity: 0.14, transform: 'scale(1.05)'}}
      />
      <PaperTexture dark />
      <div
        style={{
          position: 'absolute',
          left: 165,
          top: 115,
          width: 500,
          height: 790,
          overflow: 'hidden',
          borderRadius: 26,
          border: '1px solid rgba(101,206,179,.3)',
          background: COLORS.card,
          boxShadow: '0 40px 90px rgba(0,0,0,.35)',
          opacity: panel,
          transform: `perspective(1200px) translateX(${(1 - panel) * -140}px) rotateY(${(1 - panel) * 12}deg)`,
        }}
      >
        <Img src={staticFile('screens/ai-question-panel.png')} style={{width: '100%', height: '100%', objectFit: 'cover', objectPosition: 'top'}} />
        <div
          style={{
            position: 'absolute',
            left: 0,
            right: 0,
            top: `${8 + scan * 82}%`,
            height: 3,
            background: 'linear-gradient(90deg, transparent, #65ceb3, transparent)',
            boxShadow: '0 0 24px #65ceb3',
            opacity: frame < 93 ? 0.9 : 0,
          }}
        />
      </div>
      <div style={{position: 'absolute', left: 790, right: 150, top: 150}}>
        <div style={{color: '#65ceb3', font: `900 32px ${MONO}`, letterSpacing: '.08em'}}>POLICY GATE / FOUR CHECKS</div>
        <div style={{marginTop: 16, color: '#fff', font: `900 64px ${FONT}`, lineHeight: 1.17, letterSpacing: '-.055em'}}>AI가 답하기 전에,<br />먼저 검증합니다.</div>
        <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginTop: 38}}>
          {guards.map((label, index) => <Gate key={label} label={label} index={index} frame={frame} />)}
        </div>
        <div
          style={{
            marginTop: 26,
            padding: '17px 22px',
            borderLeft: '5px solid #65ceb3',
            background: 'rgba(101,206,179,.09)',
            color: '#cfe4dc',
            opacity: interpolate(frame, [72, 84], [0, 1], clamp),
            font: `800 32px ${FONT}`,
          }}
        >
          검증을 통과한 근거만 표시 · 실패하면 안전한 OpenDART 근거로 대체
        </div>
      </div>
    </AbsoluteFill>
  );
};

type FloatCardProps = {src: string; x: number; y: number; w: number; h: number; rotate: number; cue: number; frame: number};
const FloatCard = ({src, x, y, w, h, rotate, cue, frame}: FloatCardProps) => {
  const t = interpolate(frame, [cue, cue + 17], [0, 1], {...clamp, easing: springEase});
  return (
    <div
      style={{
        position: 'absolute',
        left: x,
        top: y,
        width: w,
        height: h,
        overflow: 'hidden',
        borderRadius: 17,
        border: '1px solid rgba(220,230,223,.8)',
        background: COLORS.card,
        opacity: t * 0.58,
        transform: `translate(${(1 - t) * (x < 960 ? -260 : 260)}px, ${(1 - t) * (y < 540 ? -150 : 150)}px) rotate(${rotate + (1 - t) * 8}deg) scale(${0.88 + t * 0.12})`,
        boxShadow: '0 28px 65px rgba(0,0,0,.2)',
      }}
    >
      <Img src={staticFile(`screens/${src}`)} style={{width: '100%', height: '100%', objectFit: 'cover', objectPosition: 'top'}} />
    </div>
  );
};

export const OutroScene = () => {
  const frame = useCurrentFrame();
  const duration = SHOTS.outro.duration;
  const cards = [
    {src: 'tab-overview.png', x: 30, y: 40, w: 690, h: 388, rotate: -5, cue: 2},
    {src: 'tab-compare.png', x: 1210, y: 45, w: 690, h: 388, rotate: 5, cue: 11},
    {src: 'tab-strategy.png', x: 5, y: 650, w: 710, h: 399, rotate: 4, cue: 17},
    {src: 'strategy-evidence.png', x: 1210, y: 650, w: 700, h: 394, rotate: -4, cue: 21},
  ];
  const mark = interpolate(frame, [42, 58], [0, 1], {...clamp, easing: springEase});
  const letters = 'DART HR Briefing'.split('');
  const rule = interpolate(frame, [72, 84], [0, 1], {...clamp, easing: ease});
  const cta = interpolate(frame, [84, 98], [0, 1], clamp);
  const fade = interpolate(frame, [duration - 10, duration], [1, 0], clamp);
  return (
    <AbsoluteFill style={{background: COLORS.ink, overflow: 'hidden', opacity: fade}}>
      <PaperTexture dark />
      {cards.map((card) => <FloatCard key={card.src} {...card} frame={frame} />)}
      <AbsoluteFill style={{background: 'radial-gradient(circle at 50% 50%, rgba(23,49,47,.2), rgba(23,49,47,.92) 62%)'}} />
      <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center'}}>
        <div style={{display: 'flex', alignItems: 'center', gap: 28, opacity: mark, transform: `scale(${0.9 + mark * 0.1})`}}>
          <BrandMark size={88} />
          <div style={{display: 'flex', color: 'white', font: `900 102px ${FONT}`, letterSpacing: '-.06em'}}>
            {letters.map((char, index) => {
              const t = interpolate(frame, [49 + index * 1.7, 58 + index * 1.7], [0, 1], {...clamp, easing: springEase});
              return (
                <span key={`${char}-${index}`} style={{whiteSpace: 'pre', opacity: t, transform: `translateY(${(1 - t) * 24}px)`, display: 'inline-block'}}>{char}</span>
              );
            })}
          </div>
        </div>
        <div style={{width: 330, height: 7, marginTop: 38, borderRadius: 10, background: '#65ceb3', transform: `scaleX(${rule})`}} />
        <div style={{marginTop: 28, color: '#d4e5de', opacity: cta, font: `800 38px ${FONT}`, letterSpacing: '-.03em'}}>공시 데이터를, 확인 가능한 HR 브리핑으로.</div>
        <div
          style={{
            marginTop: 27,
            padding: '13px 22px',
            borderRadius: 999,
            border: '1px solid rgba(101,206,179,.45)',
            background: 'rgba(101,206,179,.1)',
            color: '#8be0c5',
            opacity: cta,
            font: `800 34px ${MONO}`,
            letterSpacing: '.06em',
          }}
        >
          dart-ruby-zeta.vercel.app
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

const shot = (from: number, duration: number, child: ReactNode) => (
  <Sequence from={from} durationInFrames={duration}>{child}</Sequence>
);

export const SFX = [
  {from: 8, src: 'air-zoom-vacuum.mp3', volume: 0.35, duration: 70},
  {from: 76, src: 'sweep-fast.mp3', volume: 0.44, duration: 80},
  {from: 118, src: 'data-scan.mp3', volume: 0.23, duration: 88},
  {from: 220, src: 'sweep-fast-small.mp3', volume: 0.36, duration: 55},
  {from: 277, src: 'impact-deep-whoosh.mp3', volume: 0.4, duration: 75},
  {from: 304, src: 'sweep-fast-small.mp3', volume: 0.34, duration: 35},
  {from: 366, src: 'data-compute.mp3', volume: 0.22, duration: 80},
  {from: 487, src: 'camera-shutter-hard.mp3', volume: 0.42, duration: 32},
  {from: 465, src: 'whoosh-swirl.mp3', volume: 0.38, duration: 80},
  {from: 565, src: 'sweep-fast-small.mp3', volume: 0.35, duration: 55},
  {from: 620, src: 'data-scan.mp3', volume: 0.24, duration: 90},
  {from: 725, src: 'sweep-fast-small.mp3', volume: 0.35, duration: 50},
  {from: 775, src: 'impact-deep-whoosh.mp3', volume: 0.38, duration: 75},
  {from: 817, src: 'data-compute.mp3', volume: 0.23, duration: 68},
  {from: 850, src: 'ui-confirm-tone.mp3', volume: 0.33, duration: 35},
  {from: 885, src: 'sweep-fast-small.mp3', volume: 0.35, duration: 55},
  {from: 940, src: 'stardust-swish.mp3', volume: 0.3, duration: 95},
  {from: 980, src: 'impact-deep-whoosh.mp3', volume: 0.46, duration: 75},
  {from: 1022, src: 'sweep-fast-small.mp3', volume: 0.36, duration: 35},
] as const;

export const FLASHES = [275, 620, 940];

export const CAPTIONS = [
  {from: 116, duration: 69, text: 'OPENDART · 직원 · 보상 · 재무'},
  {from: 318, duration: 80, text: '동일 연도 · 동일 보고서 · 최대 8개 기업'},
  {from: 480, duration: 64, text: 'SIDE BY SIDE · 수치와 데이터 없음까지 함께'},
  {from: 637, duration: 70, text: 'DECISION BRIEF · QUALITY GATE · SOURCE LINKS'},
  {from: 793, duration: 74, text: 'PRIVACY · EVIDENCE · CAUSALITY · JUDGMENT'},
] as const;

export const DartPromo = () => (
  <AbsoluteFill style={{background: COLORS.paper, fontFamily: FONT}}>
    {SFX.map((item, index) => (
      <Sequence key={`sfx-${index}`} from={item.from} durationInFrames={item.duration}>
        <Audio src={staticFile(`audio/${item.src}`)} volume={item.volume} />
      </Sequence>
    ))}
    {shot(SHOTS.opening.from, SHOTS.opening.duration, <OpeningScene />)}
    {shot(SHOTS.title1.from, SHOTS.title1.duration, <TitleCard duration={SHOTS.title1.duration} text="기업을 찾는 시간에서, *비교하는* 시간으로." sub="SEARCH ONCE · COMPARE ON THE SAME BASIS" />)}
    {shot(SHOTS.compare.from, SHOTS.compare.duration, <CompareScene />)}
    {shot(SHOTS.detail.from, SHOTS.detail.duration, <DetailScene />)}
    {shot(SHOTS.title2.from, SHOTS.title2.duration, <TitleCard duration={SHOTS.title2.duration} text="수치만 *보여주지* 않습니다." sub="FACTS · LIMITS · NEXT QUESTIONS" />)}
    {shot(SHOTS.strategy.from, SHOTS.strategy.duration, <StrategyScene />)}
    {shot(SHOTS.title3.from, SHOTS.title3.duration, <TitleCard duration={SHOTS.title3.duration} text="질문은 AI에게, 판단은 *근거와* 함께." sub="AI BRIEFING WITH POLICY GUARDS" />)}
    {shot(SHOTS.ai.from, SHOTS.ai.duration, <AiScene />)}
    {shot(SHOTS.title4.from, SHOTS.title4.duration, <TitleCard duration={SHOTS.title4.duration} text="같은 기준. 확인 가능한 출처. 더 나은 *HR_질문.*" sub="FROM DISCLOSURE TO DECISION-READY QUESTIONS" />)}
    {shot(SHOTS.outro.from, SHOTS.outro.duration, <OutroScene />)}
    {CAPTIONS.map((item) => (
      <Sequence key={item.from} from={item.from} durationInFrames={item.duration}>
        <Caption text={item.text} duration={item.duration} />
      </Sequence>
    ))}
    {FLASHES.map((at) => (
      <Sequence key={at} from={at - 5} durationInFrames={10}>
        <FlashCut />
      </Sequence>
    ))}
  </AbsoluteFill>
);
