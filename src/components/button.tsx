import { Pressable, StyleSheet, Text, type PressableProps, type ViewStyle } from 'react-native';

import { Colors, Fonts, Radius } from '@/constants/theme';

type Props = Omit<PressableProps, 'style' | 'children'> & {
  title: string;
  variant?: 'primary' | 'outline' | 'outlineLight';
  style?: ViewStyle;
};

export function Button({ title, variant = 'primary', style, disabled, ...rest }: Props) {
  return (
    <Pressable
      accessibilityRole="button"
      disabled={disabled}
      style={({ pressed }) => [
        styles.base,
        styles[variant],
        (pressed || disabled) && { opacity: disabled ? 0.5 : 0.85 },
        style,
      ]}
      {...rest}>
      <Text style={[styles.label, variant === 'outline' && { color: Colors.primary }]}>{title}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    height: 54,
    borderRadius: Radius.md,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 20,
  },
  primary: { backgroundColor: Colors.primary },
  outline: { borderWidth: 1.5, borderColor: Colors.primary, backgroundColor: Colors.white },
  outlineLight: { borderWidth: 1.5, borderColor: 'rgba(255,255,255,0.7)' },
  label: { fontFamily: Fonts.bold, fontSize: 16, color: Colors.white },
});
