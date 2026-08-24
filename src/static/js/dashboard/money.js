export const preciseDecimalPlaces = 8;
export const moneyDecimalPlaces = 2;

function decimalScale(decimalPlaces) {
    return 10n ** BigInt(decimalPlaces);
}

export function parseScaledAmount(value, decimalPlaces, round = true) {
    const rawValue = String(value ?? "").trim();
    if (!rawValue) return 0n;

    const match = rawValue.match(/^(\d*)(?:\.(\d*))?$/);
    if (!match || (!match[1] && !match[2])) return 0n;

    const wholePart = match[1] || "0";
    const fractionPart = match[2] || "";
    const scale = decimalScale(decimalPlaces);
    const normalizedFraction = fractionPart.padEnd(decimalPlaces + 1, "0");
    const keptFraction = normalizedFraction.slice(0, decimalPlaces) || "0";
    const nextDigit = Number(normalizedFraction[decimalPlaces] || "0");

    let scaledValue = BigInt(wholePart) * scale + BigInt(keptFraction);
    if (round && nextDigit >= 5) {
        scaledValue += 1n;
    }

    return scaledValue;
}

export function parseQuantity(value) {
    const rawValue = String(value ?? "").trim();
    if (!/^\d+$/.test(rawValue)) return 0n;
    return BigInt(rawValue);
}

function formatScaledAmount(scaledValue, decimalPlaces) {
    const scale = decimalScale(decimalPlaces);
    const isNegative = scaledValue < 0n;
    const absoluteValue = isNegative ? -scaledValue : scaledValue;
    const wholePart = absoluteValue / scale;
    const fractionPart = String(absoluteValue % scale)
        .padStart(decimalPlaces, "0")
        .replace(/0+$/, "");
    const sign = isNegative ? "-" : "";

    return fractionPart ? `${sign}${wholePart}.${fractionPart}` : `${sign}${wholePart}`;
}

function roundScaledAmount(scaledValue, fromDecimalPlaces, toDecimalPlaces) {
    if (fromDecimalPlaces === toDecimalPlaces) {
        return scaledValue;
    }

    if (fromDecimalPlaces < toDecimalPlaces) {
        return scaledValue * decimalScale(toDecimalPlaces - fromDecimalPlaces);
    }

    const divisor = decimalScale(fromDecimalPlaces - toDecimalPlaces);
    const halfDivisor = divisor / 2n;

    if (scaledValue < 0n) {
        return (scaledValue - halfDivisor) / divisor;
    }
    return (scaledValue + halfDivisor) / divisor;
}

export function formatPreciseAmount(scaledValue) {
    return formatScaledAmount(scaledValue, preciseDecimalPlaces);
}

export function formatMoneyFromPreciseAmount(scaledValue) {
    const cents = roundScaledAmount(
        scaledValue,
        preciseDecimalPlaces,
        moneyDecimalPlaces
    );
    return formatScaledAmount(cents, moneyDecimalPlaces);
}

export function parseMoneyCents(value) {
    return parseScaledAmount(value, moneyDecimalPlaces);
}

export function parseMoneyCentsFloor(value) {
    return parseScaledAmount(value, moneyDecimalPlaces, false);
}

export function formatMoneyCents(cents) {
    return formatScaledAmount(cents, moneyDecimalPlaces);
}

export function formatMoneyInput(input) {
    if (!input.value.trim()) return;
    input.value = formatMoneyCents(parseMoneyCents(input.value));
}

export function todayIsoDate() {
    const today = new Date();
    const year = today.getFullYear();
    const month = String(today.getMonth() + 1).padStart(2, "0");
    const day = String(today.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
}
