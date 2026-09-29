import { Ionicons } from '@expo/vector-icons';
import { Pressable, StyleSheet, TextInput, View } from 'react-native';

import { Colors, Fonts, Radius, Shadow } from '@/constants/theme';

type Props = {
  value: string;
  onChangeText: (text: string) => void;
  onSubmit: () => void;
};

/** The "describe your ideal place" input with the sparkle and send button. */
export function SearchBox({ value, onChangeText, onSubmit }: Props) {
  const canSend = value.trim().length > 0;
  return (
    <View style={styles.box}>
      <Ionicons name="sparkles" size={20} color={Colors.primary} />
      <TextInput
        value={value}
        onChangeText={onChangeText}
        onSubmitEditing={() => canSend && onSubmit()}
        placeholder="e.g. 2 bedroom house in Gaborone under P5,000"
        placeholderTextColor={Colors.textMuted}
        returnKeyType="search"
        multiline
        submitBehavior="submit"
        style={styles.input}
        accessibilityLabel="Describe the place you are looking for"
      />
      <Pressable
        onPress={onSubmit}
        disabled={!canSend}
        accessibilityRole="button"
        accessibilityLabel="Search"
        style={[styles.send, !canSend && { opacity: 0.4 }]}>
        <Ionicons name="send" size={18} color={Colors.white} />
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  box: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingLeft: 18,
    paddingRight: 10,
    paddingVertical: 10,
    borderRadius: Radius.xl,
    backgroundColor: Colors.white,
    ...Shadow.card,
  },
  input: {
    flex: 1,
    minHeight: 44,
    maxHeight: 96,
    fontFamily: Fonts.medium,
    fontSize: 16,
    color: Colors.text,
    paddingTop: 12,
  },
  send: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: Colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
