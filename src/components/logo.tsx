import Svg, { Path, Rect } from 'react-native-svg';
import { StyleSheet, Text, View } from 'react-native';

import { Colors, Fonts } from '@/constants/theme';

type MarkProps = {
  size?: number;
  /** Colour of the roof line (navy on light backgrounds, white on dark). */
  roofColor?: string;
  /** Colour of the location pin. */
  pinColor?: string;
  /** Colour of the four-pane window inside the pin. */
  windowColor?: string;
};

/**
 * The Rent Me symbol: a house roof with chimney over a location pin
 * that holds a four-pane window (Brand Guideline §02).
 */
export function LogoMark({
  size = 40,
  roofColor = Colors.navy,
  pinColor = Colors.primary,
  windowColor = Colors.white,
}: MarkProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 100 100">
      {/* Roof with chimney */}
      <Path
        d="M8 50 L50 14 L92 50"
        stroke={roofColor}
        strokeWidth={9}
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
      <Rect x={69} y={18} width={9} height={17} rx={1.5} fill={roofColor} />
      {/* Location pin */}
      <Path
        d="M50 34 C35.6 34 25 44.6 25 58.5 C25 74 42 87 50 95 C58 87 75 74 75 58.5 C75 44.6 64.4 34 50 34 Z"
        fill={pinColor}
      />
      {/* Four-pane window */}
      <Rect x={41.5} y={50} width={7.5} height={7.5} rx={1.6} fill={windowColor} />
      <Rect x={51} y={50} width={7.5} height={7.5} rx={1.6} fill={windowColor} />
      <Rect x={41.5} y={59.5} width={7.5} height={7.5} rx={1.6} fill={windowColor} />
      <Rect x={51} y={59.5} width={7.5} height={7.5} rx={1.6} fill={windowColor} />
    </Svg>
  );
}

type LogoProps = {
  size?: number;
  /** `dark` = for use on navy/photo backgrounds (white roof and "Rent"). */
  variant?: 'light' | 'dark';
  tagline?: boolean;
};

/** Symbol + "Rent Me" wordmark (+ optional tagline). */
export function Logo({ size = 32, variant = 'light', tagline = false }: LogoProps) {
  const ink = variant === 'dark' ? Colors.white : Colors.navy;
  return (
    <View style={styles.row}>
      <LogoMark size={size * 1.15} roofColor={ink} />
      <View>
        <Text style={[styles.word, { fontSize: size * 0.82, color: ink }]}>
          Rent <Text style={{ color: Colors.primary }}>Me</Text>
        </Text>
        {tagline && (
          <Text style={[styles.tagline, { fontSize: size * 0.3, color: ink }]}>
            Find a place. Call it home.
          </Text>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  word: { fontFamily: Fonts.extrabold, letterSpacing: -0.5 },
  tagline: { fontFamily: Fonts.regular, marginTop: -2 },
});
