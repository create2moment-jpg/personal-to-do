import { type CollisionDetection, closestCorners, type KeyboardCoordinateGetter, pointerWithin } from "@dnd-kit/core";
import { sortableKeyboardCoordinates } from "@dnd-kit/sortable";

/**
 * Keyboard drag across columns: ←/→ jump to the neighbouring droppable column
 * (any id in `columnIds`), ↑/↓ reorder within a column (dnd-kit default).
 */
export function columnCoordinates(columnIds: () => string[]): KeyboardCoordinateGetter {
  return (event, args) => {
    const { collisionRect, droppableRects, droppableContainers } = args.context;
    if ((event.code === "ArrowRight" || event.code === "ArrowLeft") && collisionRect) {
      event.preventDefault();
      const ids = columnIds();
      const right = event.code === "ArrowRight";
      const target = droppableContainers
        .getEnabled()
        .filter((c) => ids.includes(String(c.id)))
        .map((c) => droppableRects.get(c.id))
        .filter((r): r is NonNullable<typeof r> => !!r && (right ? r.left > collisionRect.left + 20 : r.left < collisionRect.left - 20))
        .sort((a, b) => Math.abs(a.left - collisionRect.left) - Math.abs(b.left - collisionRect.left))[0];
      return target ? { x: target.left + 8, y: target.top + 44 } : args.currentCoordinates;
    }
    return sortableKeyboardCoordinates(event, args);
  };
}

/**
 * Collision strategy chosen by input: pointer drags drop where the pointer is
 * (so a wide card lands on the narrow column under the cursor); keyboard drags
 * use geometry, because dnd-kit has no live pointer position for them.
 * Call `track(event.activatorEvent)` from onDragStart.
 */
export function inputAwareCollision(): { detect: CollisionDetection; track: (e: Event) => void } {
  let keyboard = false;
  return {
    track: (e) => {
      keyboard = e instanceof KeyboardEvent;
    },
    detect: (args) => {
      if (!keyboard) {
        const hits = pointerWithin(args);
        if (hits.length > 0) return hits;
      }
      return closestCorners(args);
    },
  };
}
