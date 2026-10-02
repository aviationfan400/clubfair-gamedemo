from dataclasses import dataclass
import heapq
import math
from pygame import Vector2

@dataclass
class Boulder:
    position: Vector2
    radius: float

def segment_clear(start, end, boulders, clearance):
    delta = end - start
    length_squared = delta.length_squared()
    for rock in boulders:
        t = max(0, min(1, (rock.position - start).dot(delta) / length_squared)) if length_squared else 0
        if (start + delta * t - rock.position).length_squared() < (rock.radius + clearance) ** 2:
            return False
    return True


def free_position(position, radius, boulders):
    position = Vector2(position)
    for _ in range(4):
        changed = False
        for rock in boulders:
            delta = position - rock.position
            minimum = radius + rock.radius + 0.01
            distance = delta.length()
            if distance < minimum:
                normal = delta / distance if distance else Vector2(1, 0)
                position = rock.position + normal * minimum
                changed = True
        if not changed:
            break
    return position


def move_and_slide(position, displacement, radius, boulders, bounds=None):
    position = Vector2(position)
    steps = max(1, math.ceil(displacement.length() / max(1, radius * 0.5)))
    step = displacement / steps
    for _ in range(steps):
        position = free_position(position + step, radius, boulders)
        if bounds is not None:
            width, height = bounds
            position.x = max(radius, min(width - radius, position.x))
            position.y = max(radius, min(height - radius, position.y))
    return position


class Navigator:
    def __init__(self, boulders, radius):
        self.boulders = boulders
        self.clearance = radius + 1
        self.nodes = []
        # Circumscribed rings keep the straight chords outside each expanded rock.
        count = 16
        for rock in boulders:
            ring = (rock.radius + radius + 5) / math.cos(math.pi / count)
            for i in range(count):
                angle = i * math.tau / count
                point = rock.position + Vector2(math.cos(angle), math.sin(angle)) * ring
                if segment_clear(point, point, boulders, self.clearance):
                    self.nodes.append(point)
        self.edges = [[] for _ in self.nodes]
        for i, start in enumerate(self.nodes):
            for j in range(i):
                end = self.nodes[j]
                if self.clear(start, end):
                    distance = start.distance_to(end)
                    self.edges[i].append((j, distance))
                    self.edges[j].append((i, distance))

    def clear(self, start, end):
        return segment_clear(start, end, self.boulders, self.clearance)

    def route(self, start, goal):
        # Find the shortest visible waypoint route, including around several rocks.
        goal = free_position(goal, self.clearance + 1, self.boulders)
        if self.clear(start, goal):
            return [goal]
        distances, parents, queue = {}, {}, []
        goal_edges = {}
        for i, node in enumerate(self.nodes):
            if self.clear(start, node):
                distances[i] = start.distance_to(node)
                parents[i] = None
                heapq.heappush(queue, (distances[i], i))
            if self.clear(node, goal):
                goal_edges[i] = node.distance_to(goal)
        best, last = float("inf"), None
        while queue:
            distance, i = heapq.heappop(queue)
            if distance != distances[i] or distance >= best:
                continue
            if i in goal_edges and distance + goal_edges[i] < best:
                best, last = distance + goal_edges[i], i
            for j, cost in self.edges[i]:
                candidate = distance + cost
                if candidate < distances.get(j, float("inf")):
                    distances[j], parents[j] = candidate, i
                    heapq.heappush(queue, (candidate, j))
        if last is None:
            return []
        path = [goal]
        while last is not None:
            path.append(Vector2(self.nodes[last]))
            last = parents[last]
        return list(reversed(path))
