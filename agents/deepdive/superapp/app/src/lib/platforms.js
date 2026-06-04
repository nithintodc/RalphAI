export const PLATFORM_SECTIONS = [
  { key: 'combined', label: 'Combined' },
  { key: 'dd', label: 'DoorDash' },
  { key: 'ue', label: 'UberEats' },
];

export const DATA_PLATFORM_SECTIONS = PLATFORM_SECTIONS.filter(section => section.key !== 'combined');
